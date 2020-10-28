import os
import unittest

from conans.paths import CONANINFO
from conans.test.utils.tools import TestClient
from conans.util.files import load


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
    default_options= "shared=False"
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
    default_options = "shared=False"

    def requirements(self):
        self.requires("zlib/0.1@lasote/testing")
        self.options["zlib"].shared = self.options.shared
"""
        files = {"conanfile.py": boost}
        client.save(files, clean_first=True)
        client.run("export . lasote/testing")

        files = {"conanfile.txt": "[requires]\nBoostDbg/1.0@lasote/testing"}
        client.save(files, clean_first=True)
        client.run("install . -o BoostDbg:shared=True --build=missing")
        conaninfo = client.load(CONANINFO)
        self.assertIn("zlib:shared=True", conaninfo)
