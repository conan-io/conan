import unittest
from conans.test.utils.tools import TestClient


class RemoveSubsettingTest(unittest.TestCase):

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
