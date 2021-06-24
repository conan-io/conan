import os
import unittest

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class RemoveEmptyDirsTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("export . lasote/stable")
        rrev = client.cache.get_latest_rrev(ConanFileReference.loads("Hello/0.1@lasote/stable"))
        ref_layout = client.cache.ref_layout(rrev)
        self.assertTrue(os.path.exists(ref_layout.base_folder))
        client.run("remove Hello* -f")
        self.assertFalse(os.path.exists(ref_layout.base_folder))

    def test_shared_folder(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile("Hello", "0.1")})
        client.run("export . lasote/stable")
        rrev = client.cache.get_latest_rrev(ConanFileReference.loads("Hello/0.1@lasote/stable"))
        ref_layout = client.cache.ref_layout(rrev)
        self.assertTrue(os.path.exists(ref_layout.base_folder))
        client.run("export . lasote2/stable")
        rrev2 = client.cache.get_latest_rrev(ConanFileReference.loads("Hello/0.1@lasote2/stable"))
        ref_layout2 = client.cache.ref_layout(rrev2)
        self.assertTrue(os.path.exists(ref_layout2.base_folder))
        client.run("remove Hello/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(ref_layout.base_folder))
        self.assertTrue(os.path.exists(ref_layout2.base_folder))
