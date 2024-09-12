import os
import unittest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class RemoveEmptyDirsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        ref_layout = client.exported_layout()
        self.assertTrue(os.path.exists(ref_layout.base_folder))
        client.run("remove hello* -c")
        self.assertFalse(os.path.exists(ref_layout.base_folder))

    def test_shared_folder(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("hello", "0.1")})
        client.run("export . --user=lasote --channel=stable")
        ref_layout = client.exported_layout()
        self.assertTrue(os.path.exists(ref_layout.base_folder))
        client.run("export . --user=lasote2 --channel=stable")
        ref_layout2 = client.exported_layout()
        self.assertTrue(os.path.exists(ref_layout2.base_folder))
        client.run("remove hello/0.1@lasote/stable -c")
        self.assertFalse(os.path.exists(ref_layout.base_folder))
        self.assertTrue(os.path.exists(ref_layout2.base_folder))
