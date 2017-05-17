import unittest
from conans.test.utils.tools import TestClient
from conans.paths import CONANINFO
from conans.util.files import load
import os


class OptionTest(unittest.TestCase):

    def parsing_test(self):
        client = TestClient()
        conanfile = '''
from conans import ConanFile
class EqualerrorConan(ConanFile):
    name = "equal"
    version = "1.0.0"
    options = {"opt": "ANY"}

    def build(self):
        self.output.warn("OPTION %s" % self.options.opt)
'''
        client.save({"conanfile.py": conanfile})
        client.run("export user/testing")
        conanfile = '''
[requires]
equal/1.0.0@user/testing
[options]
equal:opt=a=b
'''
        client.save({"conanfile.txt": conanfile}, clean_first=True)
        client.run("install . --build=missing")
        self.assertIn("OPTION a=b", client.user_io.out)

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
