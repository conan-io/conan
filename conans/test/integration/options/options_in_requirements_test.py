import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.utils.tools import TestClient


class ChangeOptionsInRequirementsTest(unittest.TestCase):
    """ This test serves to check that the requirements() method can also define
    options for its dependencies, just in case they were just added
    """

    def test_basic(self):
        client = TestClient()
        zlib = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "zlib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options={"shared": False}
'''

        files = {"conanfile.py": zlib}
        client.save(files)
        client.run("export . lasote/testing")

        boost = """from conans import ConanFile
from conans import tools
import platform, os, sys

class BoostConan(ConanFile):
    name = "BoostDbg"
    version = "1.0"
    options = {"shared": [True, False]}
    default_options ={"shared": False}

    def requirements(self):
        self.requires("zlib/0.1@lasote/testing")
        self.options["zlib"].shared = self.options.shared
"""
        files = {"conanfile.py": boost}
        client.save(files, clean_first=True)
        client.run("create . lasote/testing -o BoostDbg:shared=True --build=missing")
        ref = ConanFileReference.loads("BoostDbg/1.0@lasote/testing")
        pref = client.get_latest_prev(ref)
        pkg_folder = client.get_latest_pkg_layout(pref).package()
        conaninfo = client.load(os.path.join(pkg_folder, "conaninfo.txt"))
        self.assertIn("zlib:shared=True", conaninfo)
