import os
import unittest

from conans.paths import CONANFILE, CONANFILE_TXT
from conans.test.utils.tools import TestClient


class InstallCWDTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient(users={"myremote": [("lasote", "mypass")]})
        conanfile = """
import os
from conans import ConanFile, tools, CMake

class MyLib(ConanFile):
    name = "MyLib"
    version = "0.1"
    exports = "*"
    settings = "os", "compiler", "arch", "build_type"
    generators = "cmake"

    def build(self):
        pass
"""
        self.client.save({CONANFILE: conanfile})
        self.client.run("export . lasote/stable")

    def test_install_cwd(self):
        self.client.save({CONANFILE_TXT: "[requires]MyLib/0.1@lasote/stable"}, clean_first=True)
        os.mkdir(os.path.join(self.client.current_folder, "new"))
        self.client.run("install . --install-folder new -g cmake")
        self.assertTrue(os.path.join(self.client.current_folder, "new", "conanbuildinfo.cmake"))

    def install_ref(self):
        self.client.run("install MyLib/0.1@lasote/stable --build=missing")
        self.assertEqual(["conanfile.py"], os.listdir(self.client.current_folder))
