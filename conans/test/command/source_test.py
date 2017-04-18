import unittest
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.util.files import load
import os


class SourceTest(unittest.TestCase):

    def basic_source_test(self):
        conanfile = '''
from conans import ConanFile

class ConanLib(ConanFile):
    name = "Hello"
    version = "0.1"

    def source(self):
        self.output.info("Running source!")
'''
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export lasote/stable")
        client.run("source Hello/0.1@lasote/stable")
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)

        # The second call shouldn't have effect
        client.run("source Hello/0.1@lasote/stable")
        self.assertNotIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertNotIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)

        # Forced should have effect
        client.run("source Hello/0.1@lasote/stable --force")
        self.assertIn("WARN: Forced removal of source folder", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Configuring sources", client.user_io.out)
        self.assertIn("Hello/0.1@lasote/stable: Running source!", client.user_io.out)

    def local_source_test(self):
        conanfile = '''
from conans import ConanFile
from conans.util.files import save

class ConanLib(ConanFile):

    def source(self):
        self.output.info("Running source!")
        err
        save("file1.txt", "Hello World")
'''
        # First, failing source()
        client = TestClient()
        client.save({CONANFILE: conanfile})

        client.run("source .", ignore_error=True)
        self.assertIn("PROJECT: Running source!", client.user_io.out)
        self.assertIn("ERROR: PROJECT: Error in source() method, line 9", client.user_io.out)

        # Fix the error and repeat
        client.save({CONANFILE: conanfile.replace("err", "")})
        client.run("source .")
        self.assertIn("PROJECT: Configuring sources in", client.user_io.out)
        self.assertIn("PROJECT: WARN: Your previous source command failed", client.user_io.out)
        self.assertIn("PROJECT: Running source!", client.user_io.out)
        self.assertEqual("Hello World", load(os.path.join(client.current_folder, "file1.txt")))
