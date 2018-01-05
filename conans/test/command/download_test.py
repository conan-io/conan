import unittest
import os
from conans.model.manifest import FileTreeManifest
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONAN_MANIFEST, CONANINFO
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save


class DownloadTest(unittest.TestCase):

    def download_reference_without_packages_test(self):
        server = TestServer()
        servers = {"default": server}

        client = TestClient()
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . lasote/stable")

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        client.run("upload pkg/0.1@lasote/stable")
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download pkg/0.1@lasote/stable", ignore_error=True)
        # Check 'No remote binary packages found' warning
        self.assertTrue("WARN: No remote binary packages found in remote", client.out)
        # Check at least conanfile.py is downloaded
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

    def download_reference_with_all_packages_test(self):
        server = TestServer()
        servers = {"default": server}

        client = TestClient()
        client = TestClient(servers=servers, users={
                            "default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "0.1"
"""

        conan_digest = FileTreeManifest(123123123, {})
        client.save({"conanfile.py": conanfile, CONAN_MANIFEST: str(conan_digest)})
        client.run("export . lasote/stable")

        ref = ConanFileReference.loads("pkg/0.1@lasote/stable")
        self.assertTrue(os.path.exists(client.paths.conanfile(ref)))

        package_ref = PackageReference(ref, "fakeid")
        package_folder = client.paths.package(package_ref)

        save(os.path.join(package_folder, "include", "lib1.h"), "//header")
        save(os.path.join(package_folder, CONANINFO), "info")
        save(os.path.join(package_folder, CONAN_MANIFEST), "manifest")

        client.run("upload pkg/0.1@lasote/stable")
        client.run("upload %s -p %s" % (str(ref), package_ref.package_id))
        client.run("remove pkg/0.1@lasote/stable -f")
        self.assertFalse(os.path.exists(client.paths.export(ref)))

        client.run("download pkg/0.1@lasote/stable")

        # Check not 'No remote binary packages found' warning
        self.assertNotIn("WARN: No remote binary packages found in remote", client.out)
        # Check package folder created
        self.assertTrue(os.path.exists(package_folder))
        # Check at package is downloaded
        self.assertTrue(os.path.exists(os.path.join(package_folder, "include", "lib1.h")))
        print client.out
