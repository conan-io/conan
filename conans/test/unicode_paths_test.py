# -*- coding: utf-8 -*-

import unittest
from conans.test.utils.tools import TestClient
import sys

try:
    u"dataüäïñç.txt".encode(sys.getfilesystemencoding())
    good_file_system = True
except UnicodeEncodeError:
    good_file_system = False


class UnicodePathTest(unittest.TestCase):

    @unittest.skipUnless(good_file_system, "Requires Filesystem encoding")
    def basic_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    exports_sources = "*.txt"
    def package(self):
        self.copy("data*.txt", dst="data")
"""
        test_conanfile = """# -*- coding: utf-8 -*-
from conans import ConanFile
from conans.tools import load
import os
class TestPkg(ConanFile):
    def imports(self):
        self.copy("*.txt")
    def build(self):
        self.output.info("CONTENT!: %s" % load(u"data/dataüäïñç.txt"))
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     u"dataüäïñç.txt": "//any comment",
                     "test_package/conanfile.py": test_conanfile})
        client.run("create . Pkg/0.1@user/testing")
        self.assertIn("CONTENT!: //any comment", client.out)
