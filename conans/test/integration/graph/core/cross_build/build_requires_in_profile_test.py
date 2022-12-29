import textwrap

from parameterized import parameterized

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class BuildRequiresInProfileExample(CrossBuildingBaseTestCase):
    """ There is an application with a requirement 'lib', both of them need
        a tool called 'cmake' to build. This tool is defined in profile.

        All these requirements are declared in the profiles
    """

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"
            requires = "lib/testing@user/channel"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    lib = CrossBuildingBaseTestCase.library_tpl.render(name="lib")
    lib_ref = ConanFileReference.loads("lib/testing@user/channel")

    def setUp(self):
        super(BuildRequiresInProfileExample, self).setUp()
        self._cache_recipe(self.cmake_ref, self.cmake)
        self._cache_recipe(self.lib_ref, self.lib)
        self._cache_recipe(self.app_ref, self.application)

    @parameterized.expand([(True,), (False,)])
    def test_crossbuilding(self, xbuilding):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.build_requires["*"] = [ConanFileReference.loads("cmake/testing@user/channel"), ]
        profile_host.process_settings(self.cache)

        if xbuilding:
            profile_build = Profile()
            profile_build.settings["os"] = "Build"
            profile_build.process_settings(self.cache)
        else:
            profile_build = None

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 2)
        self.assertEqual(application.conanfile.name, "app")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        lib_host = application.dependencies[0].dst
        self.assertEqual(lib_host.conanfile.name, "lib")
        self.assertEqual(lib_host.context, CONTEXT_HOST)
        self.assertEqual(lib_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages (default behavior changes if we use profile_build)
        cmake_application_build = application.dependencies[1].dst
        self.assertEqual(cmake_application_build.conanfile.name, "cmake")
        self.assertEqual(cmake_application_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(cmake_application_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])

        cmake_lib_build = lib_host.dependencies[0].dst
        self.assertNotEqual(cmake_application_build, cmake_lib_build)
        self.assertEqual(cmake_lib_build.conanfile.name, "cmake")
        self.assertEqual(cmake_lib_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(cmake_lib_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])
