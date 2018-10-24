import os
import unittest

from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.conanfile import TestConanFile
from conans.util.files import save, set_dirty


class PackageIngrityTest(unittest.TestCase):

    def remove_locks_test(self):
        client = TestClient()
        client.save({"conanfile.py": str(TestConanFile())})
        client.run("create . lasote/testing")
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        conan_folder = client.client_cache.conan(ref)
        self.assertIn("locks", os.listdir(conan_folder))
        self.assertTrue(os.path.exists(conan_folder + ".count"))
        self.assertTrue(os.path.exists(conan_folder + ".count.lock"))
        error = client.run("remove * --locks", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Specifying a pattern is not supported", client.out)
        error = client.run("remove", ignore_error=True)
        self.assertTrue(error)
        self.assertIn('ERROR: Please specify a pattern to be removed ("*" for all)', client.out)
        client.run("remove --locks")
        self.assertNotIn("locks", os.listdir(conan_folder))
        self.assertFalse(os.path.exists(conan_folder + ".count"))
        self.assertFalse(os.path.exists(conan_folder + ".count.lock"))

    def upload_dirty_test(self):
        test_server = TestServer([], users={"lasote": "mypass"})
        client = TestClient(servers={"default": test_server},
                            users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": str(TestConanFile())})
        client.run("export . lasote/testing")
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        pkg_ref = PackageReference(ref, "12345")
        package_folder = client.client_cache.package(pkg_ref)
        save(os.path.join(package_folder, "conaninfo.txt"), "")
        save(os.path.join(package_folder, "conanmanifest.txt"), "")
        set_dirty(package_folder)

        error = client.run("upload * --all --confirm", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Package Hello/0.1@lasote/testing:12345 is corrupted, aborting upload", client.out)
        self.assertIn("Remove it with 'conan remove Hello/0.1@lasote/testing -p=12345'", client.out)

        client.run("remove Hello/0.1@lasote/testing -p=12345 -f")
        client.run("upload * --all --confirm")
