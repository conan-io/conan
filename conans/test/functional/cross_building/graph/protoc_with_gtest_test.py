# coding=utf-8

import textwrap
from conans.test.functional.cross_building.graph.protoc_basic_test import ClassicProtocExample
from conans.util.files import save
from conans.model.profile import Profile


class ProtocWithGTestExample(ClassicProtocExample):

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class GTest(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "application"
            version = "testing"

            settings = "os"
            
            def requirements(self):
                self.requires("protobuf/testing@user/channel")

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel", context="build")
                # Make it explicit that these should be for host_machine
                self.build_requires("protoc/testing@user/channel", context="host")
                self.build_requires("gtest/testing@user/channel", context="host")

            def build(self):
                self.output.info(">> settings.os:".format(self.settings.os))
    """)

    def setUp(self):
        super(ProtocWithGTestExample, self).setUp()
        self._cache_recipe("gtest/testing@user/channel", self.protobuf)
        self._cache_recipe("application/testing@user/channel", self.application)

        save(self.cache.settings_path, self.settings_yml)

    def test_crossbuilding(self):
        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        # Check HOST packages
        application = deps_graph.root.dependencies[0].dst
        self.assertEqual(len(application.dependencies), 4)
        self.assertEqual(application.conanfile.name, "application")
        self.assertEqual(application.build_context, "host")
        self.assertEqual(application.conanfile.settings.os, profile_host.settings['os'])

        protobuf_host = application.dependencies[0].dst
        self.assertEqual(protobuf_host.conanfile.name, "protobuf")
        self.assertEqual(protobuf_host.build_context, "host")
        self.assertEqual(protobuf_host.conanfile.settings.os, profile_host.settings['os'])

        protoc_host = application.dependencies[2].dst
        self.assertEqual(protoc_host.conanfile.name, "protoc")
        self.assertEqual(protoc_host.build_context, "host")
        self.assertEqual(protoc_host.conanfile.settings.os, profile_host.settings['os'])

        protoc_protobuf_host = protoc_host.dependencies[0].dst
        self.assertEqual(protoc_protobuf_host, protobuf_host)

        gtest_host = application.dependencies[3].dst
        self.assertEqual(gtest_host.conanfile.name, "gtest")
        self.assertEqual(gtest_host.build_context, "host")
        self.assertEqual(gtest_host.conanfile.settings.os, profile_host.settings['os'])

        # Check BUILD packages
        protoc_build = application.dependencies[1].dst
        self.assertEqual(protoc_build.conanfile.name, "protoc")
        self.assertEqual(protoc_build.build_context, "build")
        self.assertEqual(str(protoc_build.conanfile.settings.os), profile_build.settings['os'])

        protobuf_build = protoc_build.dependencies[0].dst
        self.assertEqual(protobuf_build.conanfile.name, "protobuf")
        self.assertEqual(protoc_build.build_context, "build")
        self.assertEqual(str(protobuf_build.conanfile.settings.os), profile_build.settings['os'])

