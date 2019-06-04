# coding=utf-8

import textwrap
from conans.test.functional.cross_building.graph.protoc_basic_test import ClassicProtocExample
from conans.util.files import save
from conans.model.profile import Profile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


class CrossBuilding(ClassicProtocExample):
    """ Run the build corresponding to the graph/ProtocWithGTestExample test
    """

    protobuf = textwrap.dedent("""
        from conans import ConanFile

        class Protobuf(ConanFile):
            name = "protobuf"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"

            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
    """)

    protoc = textwrap.dedent("""
        import os
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "protoc"
            version = "testing"

            settings = "os"
            requires = "protobuf/testing@user/channel"
            options = {"target": "ANY"}
            default_options = {"target": "None"}
            
            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
                self.output.info(">> options.target: {}".format(self.options.target))
                
            def package_info(self):
                if self.settings.os == "Build":
                    self.env_info.PATH.append(os.path.join(self.package_folder, "bin"))
                self.env_info.context = str(self.settings.os)                
    """)

    gtest = textwrap.dedent("""
        from conans import ConanFile

        class GTest(ConanFile):
            name = "gtest"
            version = "testing"

            settings = "os"  # , "arch", "compiler", "build_type"

            def build(self):
                self.output.info(">> settings.os: {}".format(self.settings.os))
    """)

    application = textwrap.dedent("""
        from conans import ConanFile

        class Application(ConanFile):
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
                self.output.info(">> settings.os: {}".format(self.settings.os))
                for key, value in self.deps_env_info["protoc"].vars.items():
                    self.output.info(">> protoc/env_info: {}={}".format(key, value))
                
    """)

    settings_yml = textwrap.dedent("""
        os:
            Host:
            Build:
    """)

    profile_host = textwrap.dedent("""
        [settings]
        os = Host
    """)

    profile_build = textwrap.dedent("""
        [settings]
        os = Build
    """)

    def setUp(self):
        self.t = TestClient()
        save(self.t.cache.settings_path, self.settings_yml)

        self.t.save({'protobuf.py': self.protobuf,
                     'protoc.py': self.protoc,
                     'gtest.py': self.gtest,
                     'application.py': self.application})
        self.t.run("export protobuf.py protobuf/testing@user/channel")
        self.t.run("export protoc.py protoc/testing@user/channel")
        self.t.run("export gtest.py gtest/testing@user/channel")
        self.t.run("export application.py application/testing@user/channel")

    def test_crossbuilding(self):
        self.t.save(files={"conanfile.txt": textwrap.dedent("""
                                                [requires]
                                                application/testing@user/channel
                                            """),
                           "profile_host": self.profile_host,
                           "profile_build": self.profile_build}, clean_first=True)

        self.t.run("install . -pr:h profile_host -pr:b profile_build --build=missing")
        # Check host packages
        self.assertIn("application/testing@user/channel: >> settings.os: Host", self.t.out)
        self.assertIn("protoc/testing@user/channel: >> settings.os: Host", self.t.out)
        self.assertIn("protobuf/testing@user/channel: >> settings.os: Host", self.t.out)
        # Check build packages
        self.assertIn("protoc/testing@user/channel: >> settings.os: Build", self.t.out)
        self.assertIn("protobuf/testing@user/channel: >> settings.os: Build", self.t.out)

        # Check env_info
        self.assertIn("application/testing@user/channel: >> protoc/env_info: context=Host", self.t.out)  # TODO: Here I expect to get the BR("build") one
