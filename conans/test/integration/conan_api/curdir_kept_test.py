import os
import unittest

from conans.client import tools
from conans.client.conan_api import ConanAPIV1
from conans.test.utils.test_files import temp_folder


class CurdirKeptTest(unittest.TestCase):

    def test_curdir(self):
        tmp_folder = temp_folder()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "lib"
    version = "1.0"
"""
        tools.save(os.path.join(tmp_folder, "conanfile.py"), conanfile)
        with tools.chdir(tmp_folder):
            # Needed to not write in the real computer cache
            with tools.environment_append({"CONAN_USER_HOME": tmp_folder}):
                api, _, _ = ConanAPIV1.factory()
                api.create(".", name="lib", version="1.0", user="user", channel="channel")
                self.assertEqual(tmp_folder, os.getcwd())
                api.create(".", name="lib", version="1.0", user="user", channel="channel2")
                self.assertEqual(tmp_folder, os.getcwd())
