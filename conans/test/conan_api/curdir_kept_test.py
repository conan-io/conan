import unittest
import os

from conans import tools
from conans.client.conan_api import ConanAPIV1


class CurdirKeptTest(unittest.TestCase):

    def curdir_test(self):
        tmp_folder = os.path.realpath(os.path.expanduser(tools.mkdir_tmp()))
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
