import textwrap

from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conans.model.profile import Profile
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class NoWayBackToHost(CrossBuildingBaseTestCase):

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
            name = "app"
            version = "testing"

            settings = "os"

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel")
                self.build_requires("gtest/testing@user/channel", force_host_context=True)

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    protoc = CrossBuildingBaseTestCase.protoc_tpl.render(
        build_requires=((CrossBuildingBaseTestCase.cmake_ref, False),
                        (CrossBuildingBaseTestCase.gtest_ref, True)))

    def setUp(self):
        super(NoWayBackToHost, self).setUp()
        self._cache_recipe(self.cmake_ref, self.cmake)
        self._cache_recipe(self.gtest_ref, self.gtest)
        self._cache_recipe(self.protobuf_ref, self.protobuf)
        self._cache_recipe(self.protoc_ref, self.protoc)
        self._cache_recipe(self.app_ref, self.application)

    def test_profile_access(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build,
                                       install=True)

        # - Application
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(application.conanfile.name, "app")
        self.assertEqual(application.context, CONTEXT_HOST)
        self.assertEqual(application.conanfile.settings.os, "Host")
        self.assertEqual(application.conanfile.settings_build.os, "Build")
        self.assertEqual(application.conanfile.settings_target, None)

        # - protoc
        protoc = application.dependencies[0].dst
        self.assertEqual(protoc.conanfile.name, "protoc")
        self.assertEqual(protoc.context, CONTEXT_BUILD)
        self.assertEqual(protoc.conanfile.settings.os, "Build")
        self.assertEqual(protoc.conanfile.settings_build.os, "Build")
        self.assertEqual(protoc.conanfile.settings_target.os, "Host")

        # - protoc/protobuf
        protobuf = protoc.dependencies[0].dst
        self.assertEqual(protobuf.conanfile.name, "protobuf")
        self.assertEqual(protobuf.context, CONTEXT_BUILD)
        self.assertEqual(protobuf.conanfile.settings.os, "Build")
        self.assertEqual(protobuf.conanfile.settings_build.os, "Build")
        self.assertEqual(protobuf.conanfile.settings_target.os, "Host")

        # - protoc/cmake
        cmake = protoc.dependencies[1].dst
        self.assertEqual(cmake.conanfile.name, "cmake")
        self.assertEqual(cmake.context, CONTEXT_BUILD)
        self.assertEqual(cmake.conanfile.settings.os, "Build")
        self.assertEqual(cmake.conanfile.settings_build.os, "Build")
        self.assertEqual(cmake.conanfile.settings_target.os, "Build")

        # - protoc/gtest
        protoc_gtest = protoc.dependencies[2].dst
        self.assertEqual(protoc_gtest.conanfile.name, "gtest")
        self.assertEqual(protoc_gtest.context, CONTEXT_BUILD)
        self.assertEqual(protoc_gtest.conanfile.settings.os, "Build")
        self.assertEqual(protoc_gtest.conanfile.settings_build.os, "Build")
        # We can't think about an scenario where a `build_require-host` should know about
        #   the target context. We are removing this information on purpose.
        self.assertEqual(protoc_gtest.conanfile.settings_target, None)

        # - gtest
        gtest = application.dependencies[1].dst
        self.assertEqual(gtest.conanfile.name, "gtest")
        self.assertEqual(gtest.context, CONTEXT_HOST)
        self.assertEqual(gtest.conanfile.settings.os, "Host")
        self.assertEqual(gtest.conanfile.settings_build.os, "Build")
        self.assertEqual(gtest.conanfile.settings_target, None)
