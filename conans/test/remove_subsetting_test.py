import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir
import os


class RemoveSubsettingTest(unittest.TestCase):

    def remove_options_test(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    options = {"opt1": [True, False], "opt2": [True, False]}
    default_options = "opt1=True", "opt2=False"
    def config_options(self):
        del self.options.opt2
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        client.run("build ..")

    def remove_setting_test(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "build_type"
    def configure(self):
        del self.settings.build_type

    def source(self):
        self.settings.build_type
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("source ..")  # Without install you can access build_type, no one has removed it
        client.run("install ..")
        # This raised an error because build_type wasn't defined
        client.run("build ..")

        error = client.run("source ..", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'settings.build_type' doesn't exist", client.user_io.out)

    def remove_runtime_test(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conans import ConanFile, CMake
class Pkg(ConanFile):
    settings = "os", "compiler", "arch"
    def configure(self):
        del self.settings.compiler.runtime
    def build(self):
        try:
            self.settings.compiler.runtime
        except Exception as e:
            self.output.info(str(e))
        cmake = CMake(self)
        self.output.info(cmake.command_line)
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run('install .. -s os=Windows -s compiler="Visual Studio" -s compiler.version=15 -s arch=x86')
        # This raised an error because build_type wasn't defined
        client.run("build ..")
        self.assertIn("'settings.compiler.runtime' doesn't exist for 'Visual Studio'", client.out)
        self.assertNotIn("CONAN_LINK_RUNTIME", client.out)
        self.assertIn('-DCONAN_COMPILER="Visual Studio"', client.out)

    def remove_subsetting_test(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()
        base = '''from conans import ConanFile
class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
'''
        test = """from conans import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def configure(self):
        del self.settings.compiler.libcxx

    def test(self):
        pass

    def build(self):
        cmake = CMake(self)
        self.output.info("TEST " + cmake.command_line)
"""
        client.save({"conanfile.py": base,
                     "test_package/conanfile.py": test})
        client.run("create . user/testing -s arch=x86_64 -s compiler=gcc "
                   "-s compiler.version=4.9 -s compiler.libcxx=libstdc++11")
        self.assertNotIn("LIBCXX", client.out)

    def remove_subsetting_build_test(self):
        # https://github.com/conan-io/conan/issues/2049
        client = TestClient()

        conanfile = """from conans import ConanFile, CMake
class ConanLib(ConanFile):
    settings = "compiler", "arch"

    def package(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("PACKAGE " + str(e))

    def configure(self):
        del self.settings.compiler.libcxx

    def build(self):
        try:
            self.settings.compiler.libcxx
        except Exception as e:
            self.output.error("BUILD " + str(e))
        cmake = CMake(self)
        self.output.info("BUILD " + cmake.command_line)
"""
        client.save({"conanfile.py": conanfile})
        client.run("install . -s arch=x86_64 -s compiler=gcc -s compiler.version=4.9 "
                   "-s compiler.libcxx=libstdc++11")
        client.run("build .")
        self.assertIn("ERROR: BUILD 'settings.compiler.libcxx' doesn't exist for 'gcc'",
                      client.out)
        self.assertNotIn("LIBCXX", client.out)
        client.run("package .")
        self.assertIn("ERROR: PACKAGE 'settings.compiler.libcxx' doesn't exist for 'gcc'",
                      client.out)
