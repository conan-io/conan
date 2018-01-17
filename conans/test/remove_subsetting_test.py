import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import mkdir
import os


class RemoveSubsettingTest(unittest.TestCase):

    def remove_setting_test(self):
        # https://github.com/conan-io/conan/issues/2327
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "os", "build_type"
    def configure(self):
        del self.settings.build_type
"""
        client.save({"conanfile.py": conanfile})
        build_folder = os.path.join(client.current_folder, "build")
        mkdir(build_folder)
        client.current_folder = build_folder
        client.run("install ..")
        # This raised an error because build_type wasn't defined
        client.run("build ..")

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
