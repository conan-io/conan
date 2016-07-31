import unittest
from conans.test.tools import TestClient
from conans.util.files import load
import os


class PathLengthLimitTest(unittest.TestCase):

    def basic_test(self):
        client = TestClient()
        base = '''
from conans import ConanFile
import os

class ConanLib(ConanFile):
    name = "lib"
    version = "0.1"
    short_paths2 = True
    patata = 32

    def source(self):
        extra_path = "123456789/" * 20
        print "CURRENT ", os.getcwd()
        os.makedirs(extra_path)
        myfile = os.path.join(extra_path, "myfile.txt")
        with open(path, "wb") as handle:
            handle.write("Hello extra path length")

    def build(self):
        extra_path = "123456789/" * 20
        os.makedirs(extra_path)
        myfile = os.path.join(extra_path, "myfile2.txt")
        with open(path, "wb") as handle:
            handle.write("Hello extra path length")

    def package(self):
        self.copy("*.txt", keep_path=False)
'''

        files = {"conanfile.py": base}
        client.save(files)
        client.run("export user/channel")
        client.run("install lib/0.1@user/channel --build")
        print client.user_io.out


