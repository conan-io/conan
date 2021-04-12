import textwrap

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class NoWayBackToHost(CrossBuildingBaseTestCase):
    """ There is an application that build_requires (build) a tool and it is trying to
        build_require another tool from the "host" context. As there are
        no more context changes available once we entered the 'build' context, then there is no
        way back to the original host context because build===host
    """

    build_tool = textwrap.dedent("""
        from conans import ConanFile

        class BuildTool(ConanFile):
            name = "build_tool"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                # From the perspective of this package, the "host" context is the same one
                #  as the one where `build_tool` is being built.
                self.build_requires("host_tool/testing@user/channel", force_host_context=True)

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))

            def package_info(self):
                build_tool_str = "build_tool-host" if self.settings.os == "Host" else "build_tool-build"

                self.cpp_info.includedirs = [build_tool_str, ]
                self.cpp_info.libdirs = [build_tool_str, ]
                self.cpp_info.bindirs = [build_tool_str, ]

                self.env_info.PATH.append(build_tool_str)
                self.env_info.OTHERVAR = build_tool_str
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("build_tool/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    host_tool = CrossBuildingBaseTestCase.library_tpl.render(name="host_tool")

    host_tool_ref = ConanFileReference.loads("host_tool/testing@user/channel")
    build_tool_ref = ConanFileReference.loads("build_tool/testing@user/channel")

    def setUp(self):
        super(NoWayBackToHost, self).setUp()
        self._cache_recipe(self.host_tool_ref, self.host_tool)
        self._cache_recipe(self.build_tool_ref, self.build_tool)
        self._cache_recipe(self.app_ref, self.application)

    def test_crossbuilding(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build, install=True)

        # Check HOST packages
        #   - Application
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 1)
        self.assertEqual(application.conanfile.name, "app")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        #   - Application::deps_cpp_info:
        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_cpp_info["host_tool"]
        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_cpp_info["build_tool"]

        #   - Application::deps_env_info:
        with self.assertRaises(KeyError):
            _ = application.conanfile.deps_env_info["host_tool"]
        build_tool_env_info = application.conanfile.deps_env_info["build_tool"]
        self.assertEqual(build_tool_env_info.PATH, ['build_tool-build'])
        self.assertEqual(build_tool_env_info.OTHERVAR, 'build_tool-build')

        # Check BUILD package
        #   - BuildTool
        build_tool = application.dependencies[0].dst
        self.assertEqual(build_tool.conanfile.name, "build_tool")
        self.assertEqual(build_tool.context, CONTEXT_BUILD)
        self.assertEqual(build_tool.conanfile.settings.os, profile_build.settings['os'])

        #   - BuildTool::deps_cpp_info:
        host_tool_cpp_info = build_tool.conanfile.deps_cpp_info["host_tool"]
        self.assertEqual(host_tool_cpp_info.includedirs, ['host_tool-build-testing'])
        self.assertEqual(host_tool_cpp_info.libdirs, ['host_tool-build-testing'])
        self.assertEqual(host_tool_cpp_info.bindirs, ['host_tool-build-testing'])

        #   - BuildTool::deps_env_info
        with self.assertRaises(KeyError):
            _ = build_tool.conanfile.deps_env_info["host_tool"]

        #   - HostTool
        # There is no way back to host profile from build one (host===build)
        host_tool = build_tool.dependencies[0].dst
        self.assertEqual(host_tool.conanfile.name, "host_tool")
        self.assertEqual(host_tool.context, CONTEXT_BUILD)
        self.assertEqual(str(host_tool.conanfile.settings.os), profile_build.settings['os'])
