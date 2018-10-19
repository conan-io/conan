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
        pass
"""
        conanfile_path = os.path.join(temp_folder(), "conanfile.py")
        tools.save(conanfile_path, conanfile)
        conan = TestConanApi()
        output = conan.export_pkg(conanfile_path, "mypackage", "testing", user="danimtb",
                                  version="0.1.0", package_folder="dist")
        self.assertEqual(output["error"], False)
        self.assertEqual(output["installed"][0]["recipe"]["id"], "mypackage/0.1.0@danimtb/testing")
        self.assertEqual(output["installed"][0]["recipe"]["dependency"], False)
        self.assertEqual(output["installed"][0]["packages"][0]["id"],
                         "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(output["installed"][0]["packages"][0]["built"], True)
