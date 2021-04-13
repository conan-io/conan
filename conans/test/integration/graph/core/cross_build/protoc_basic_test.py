import textwrap

from parameterized import parameterized

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class ClassicProtocExampleBase(CrossBuildingBaseTestCase):
    """ There is an application that requires the protobuf library, and also
        build_requires the protoc executable to generate some files, but protoc
        also requires the protobuf library to build.

        Expected packages:
            * host_machine: application, protobuf
            * build_machine: protoc, protobuf
    """

    application = textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"
            requires = "protobuf/testing@user/channel"

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    def setUp(self):
        super(ClassicProtocExampleBase, self).setUp()
        self._cache_recipe(self.protobuf_ref, self.protobuf)
        self._cache_recipe(self.protoc_ref, self.protoc)
        self._cache_recipe(self.app_ref, self.application)


class ClassicProtocExample(ClassicProtocExampleBase):

    @parameterized.expand([(True, ), (False, )])
    def test_crossbuilding(self, xbuilding):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        if xbuilding:
            profile_build = Profile()
            profile_build.settings["os"] = "Build"
            profile_build.process_settings(self.cache)
        else:
            profile_build = None

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build,
                                       install=True)

        # Check HOST packages
        #   - application
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 2)
        self.assertEqual(application.conanfile.name, "app")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])
        if xbuilding:
            #   - application::deps_cpp_info:
            protobuf_host_cpp_info = application.conanfile.deps_cpp_info["protobuf"]
            self.assertEqual(protobuf_host_cpp_info.includedirs, ['protobuf-host'])
            self.assertEqual(protobuf_host_cpp_info.libdirs, ['protobuf-host'])
            self.assertEqual(protobuf_host_cpp_info.bindirs, ['protobuf-host'])
            with self.assertRaises(KeyError):
                _ = application.conanfile.deps_cpp_info["protoc"]

            #   - application::deps_env_info:
            protoc_env_info = application.conanfile.deps_env_info["protoc"]
            self.assertEqual(protoc_env_info.PATH, ['protoc-build'])
            self.assertEqual(protoc_env_info.OTHERVAR, 'protoc-build')

            protobuf_env_info = application.conanfile.deps_env_info["protobuf"]
            self.assertEqual(protobuf_env_info.PATH, ['protobuf-build'])
            self.assertEqual(protobuf_env_info.OTHERVAR, 'protobuf-build')

        #   - protobuf host
        protobuf_host = application.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.context, CONTEXT_HOST)
        self.assertEqual(protobuf_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages (default behavior changes if we use profile_build)
        #   - protoc
        protoc_build = application.dependencies[1].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(protoc_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])

        #   - protobuf
        protobuf_build = protoc_build.dependencies[0].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protoc_build.context, CONTEXT_BUILD if xbuilding else CONTEXT_HOST)
        self.assertEqual(str(protobuf_build.conanfile.settings.os),
                         (profile_build if xbuilding else profile_host).settings['os'])


