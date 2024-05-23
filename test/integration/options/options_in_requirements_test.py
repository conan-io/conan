import os
import unittest

from conans.model.recipe_ref import RecipeReference
from conan.test.utils.tools import TestClient


class ChangeOptionsInRequirementsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        zlib = '''
from conan import ConanFile

class ConanLib(ConanFile):
    name = "zlib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options={"shared": False}
'''

        files = {"conanfile.py": zlib}
        client.save(files)
        client.run("export . --user=lasote --channel=testing")

        boost = """from conan import ConanFile
import platform, os, sys

class BoostConan(ConanFile):
    name = "boostdbg"
    version = "1.0"
    options = {"shared": [True, False]}
    default_options ={"shared": False}

    def configure(self):
        self.options["zlib/*"].shared = self.options.shared

    def requirements(self):
        self.requires("zlib/0.1@lasote/testing")
"""
        files = {"conanfile.py": boost}
        client.save(files, clean_first=True)
        client.run("create . --user=lasote --channel=testing -o boostdbg/*:shared=True --build=missing")
        ref = RecipeReference.loads("zlib/0.1@lasote/testing")
        pref = client.get_latest_package_reference(ref)
        pkg_folder = client.get_latest_pkg_layout(pref).package()
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))
        self.assertIn("shared=True", conaninfo)
