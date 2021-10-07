import os
import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class RemoveEmptyDirsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("export . lasote/stable")
        path = os.path.join(client.storage_folder, "Hello/0.1/lasote/stable")
        self.assertTrue(os.path.exists(path))
        client.run("remove Hello* -f")
        path = os.path.join(client.storage_folder, "Hello")
        self.assertFalse(os.path.exists(path))

    def test_shared_folder(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("export . lasote/stable")
        path = os.path.join(client.storage_folder, "Hello/0.1/lasote/stable")
        self.assertTrue(os.path.exists(path))
        client.run("export . lasote2/stable")
        path = os.path.join(client.storage_folder, "Hello/0.1/lasote2/stable")
        self.assertTrue(os.path.exists(path))
        client.run("remove Hello/0.1@lasote/stable -f")
        path = os.path.join(client.storage_folder, "Hello/0.1/lasote")
        self.assertFalse(os.path.exists(path))
        path = os.path.join(client.storage_folder, "Hello/0.1")
        self.assertTrue(os.path.exists(path))
