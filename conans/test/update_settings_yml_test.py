import unittest
from conans.test.tools import TestClient
from conans.util.files import load, save
import os


class UpdateSettingsYmlTest(unittest.TestCase):
    """ This test is to validate that after adding a new settings, that allows a None
    value, this None value does not modify exisisting packages SHAs
    """

    def test_update_settings(self):
        file_content = '''
from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    name = "test"
    version = "1.9"
    settings = "os", "compiler", "arch", "build_type"

    def source(self):
        self.output.warn("Sourcing...")

    def build(self):
        self.output.warn("Building...")
    '''
        prev_settings = """
os: [Windows, Linux, Macos, Android]
arch: [x86, x86_64, armv6, armv7, armv7hf, armv8]
compiler:
    gcc:
        version: ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3"]
    Visual Studio:
        runtime: [None, MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7"]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0"]

build_type: [None, Debug, Release]
"""
        files = {"conanfile.py": file_content}
        client = TestClient()
        save(client.paths.settings_path, prev_settings)
        conf = load(client.paths.conan_conf_path)
        conf = conf.replace("compiler.stdlib=None", "")
        self.assertNotIn("stdlib", conf)
        save(client.paths.conan_conf_path, conf)
        self.assertNotIn("stdlib", client.paths.conan_config.settings_defaults.dumps())
        client.save(files)
        client.run("export lasote/testing")
        self.assertNotIn("stdlib", load(client.paths.settings_path))
        self.assertNotIn("stdlib", load(client.paths.conan_conf_path))
        self.assertNotIn("stdlib", client.paths.conan_config.settings_defaults.dumps())

        client.run("install test/1.9@lasote/testing --build -s compiler=gcc "
                   "-s compiler.version=4.9 -s os=Windows")
        self.assertIn("425ec5c941593abc5ec9394a8eee44bcaa6409d0", client.user_io.out)
 
        #Now the new one
        files = {"conanfile.py": file_content}
        client = TestClient()    
        client.save(files)
        client.run("export lasote/testing")
        self.assertIn("stdlib", load(client.paths.settings_path))

        client.run("install test/1.9@lasote/testing --build -s compiler=gcc "
                   "-s compiler.version=4.9 -s compiler.stdlib=None -s os=Windows")
        self.assertIn("425ec5c941593abc5ec9394a8eee44bcaa6409d0", client.user_io.out)
