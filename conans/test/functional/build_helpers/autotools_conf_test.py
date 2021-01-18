import os
import stat
import textwrap
import unittest

from conans.test.utils.tools import TestClient


@unittest.skipUnless(os.name == 'posix', "requires posix environment")
class AutoToolsConfTest(unittest.TestCase):
    def test_conf(self):

        profile = textwrap.dedent("""
            include(default)
            [conf]
            tools.autotoolsbuildenvironment:host=arm-linux-gnueabihf
            tools.autotoolsbuildenvironment:build=i386-kfreebsd-gnu
            tools.autotoolsbuildenvironment:target=aarch64-none-elf
            """)

        configure = textwrap.dedent("""
            #/usr/bin/env bash
            echo $@
            """)

        conanfile_py = textwrap.dedent("""
            from conans import ConanFile, tools, AutoToolsBuildEnvironment


            class App(ConanFile):
                settings = "os", "arch", "compiler", "build_type"
                options = {"shared": [True, False], "fPIC": [True, False]}
                default_options = {"shared": False, "fPIC": True}

                def config_options(self):
                    if self.settings.os == "Windows":
                        del self.options.fPIC

                def build(self):
                    env_build = AutoToolsBuildEnvironment(self)
                    env_build.configure()
            """)

        self.t = TestClient()
        self.t.save({"conanfile.py": conanfile_py,
                     "configure": configure,
                     "profile": profile})

        filename = os.path.join(self.t.current_folder, "configure")
        os.chmod(filename, os.stat(filename).st_mode | stat.S_IXUSR)

        self.t.run("install . --profile:host=profile")
        self.t.run("build .")

        self.assertIn("--host=arm-linux-gnueabihf", self.t.out)
        self.assertIn("--build=i386-kfreebsd-gnu", self.t.out)
        self.assertIn("--target=aarch64-none-elf", self.t.out)
