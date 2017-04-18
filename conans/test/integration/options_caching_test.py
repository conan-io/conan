import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANINFO
from conans.util.files import load
import os


class OptionCachingTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        zlib = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "zlib"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options= "shared=False"
'''

        client.save({"conanfile.py": zlib})
        client.run("export lasote/testing")

        project = """[requires]
zlib/0.1@lasote/testing
"""
        client.save({"conanfile.txt": project}, clean_first=True)

        client.run("install -o zlib:shared=True --build=missing")
        self.assertIn("zlib/0.1@lasote/testing:2a623e3082a38f90cd2c3d12081161412de331b0",
                      client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        self.assertIn("zlib:shared=True", conaninfo)

        # Options not cached anymore
        client.run("install --build=missing")
        self.assertIn("zlib/0.1@lasote/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.user_io.out)
        conaninfo = load(os.path.join(client.current_folder, CONANINFO))
        self.assertNotIn("zlib:shared=True", conaninfo)
