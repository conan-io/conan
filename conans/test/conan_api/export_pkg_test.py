import os
import unittest

from conans import tools
from conans.test.utils.tools import TestConanApi
from conans.test.utils.test_files import temp_folder


class ExportPkgTest(unittest.TestCase):

    def export_pkg_output_test(self):
        conanfile = """from conans import ConanFile
class MyConan(ConanFile):
    name = "mypackage"
    version = "0.1.0"

    def package(self):
        self.copy("*.cpp", dst="sources")
        self.copy("*.lib", dst="lib")
"""
        with tools.chdir(tools.mkdir_tmp()):
            source_path = os.path.join("sources", "kk.cpp")
            build_path = os.path.join("build", "kk.lib")
            tools.save("conanfile.py", conanfile)
            tools.save(source_path, "source content")
            tools.save(build_path, "build content")

            # Deafult folders
            conan = TestConanApi()
            result = conan.export_pkg("conanfile.py", "mypackage", "testing", user="danimtb",
                                      version="0.1.0")
            self._check_result(result)
            self.assertIn("mypackage/0.1.0@danimtb/testing package(): Copied 1 '.cpp' file: kk.cpp",
                          conan.out)
            self.assertIn("mypackage/0.1.0@danimtb/testing package(): Copied 1 '.lib' file: kk.lib",
                          conan.out)

            # Without package_folder
            conan = TestConanApi()
            result = conan.export_pkg("conanfile.py", "mypackage", "testing", user="danimtb",
                                      version="0.1.0", source_folder="sources",
                                      build_folder="build")
            self._check_result(result)
            self.assertIn("mypackage/0.1.0@danimtb/testing package(): Copied 1 '.cpp' file: kk.cpp",
                          conan.out)
            self.assertIn("mypackage/0.1.0@danimtb/testing package(): Copied 1 '.lib' file: kk.lib",
                          conan.out)

            # With package_folder
            conan = TestConanApi()
            result = conan.export_pkg("conanfile.py", "mypackage", "testing", user="danimtb",
                                      version="0.1.0", package_folder="dist")
            self._check_result(result)
            self.assertIn("mypackage/0.1.0@danimtb/testing: WARN: No files copied from package "
                          "folder!", conan.out)

    def _check_result(self, result):
        self.assertEqual(result["error"], False)
        self.assertEqual(result["installed"][0]["recipe"]["id"], "mypackage/0.1.0@danimtb/testing")
        self.assertEqual(result["installed"][0]["recipe"]["dependency"], False)
        self.assertEqual(result["installed"][0]["packages"][0]["id"],
                         "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(result["installed"][0]["packages"][0]["built"], True)
