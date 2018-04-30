import unittest
import os

from conans import tools
from conans.client.conan_api import ConanAPIV1
from conans.test.utils.test_files import temp_folder


class CurdirKeptTest(unittest.TestCase):

    def curdir_test(self):
        tmp_folder = temp_folder()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "lib"
    version = "1.0"
"""
        tools.save(os.path.join(tmp_folder, "conanfile.py"), conanfile)
        with tools.chdir(tmp_folder):
            api, _, _ = ConanAPIV1.factory()
            api.create(".", name="lib", version="1.0", user="user", channel="channel")
            self.assertEquals(tmp_folder, os.getcwd())
            api.create(".", name="lib", version="1.0", user="user", channel="channel2")
            self.assertEquals(tmp_folder, os.getcwd())
