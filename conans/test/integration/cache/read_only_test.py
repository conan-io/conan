import os
import unittest

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import save


class ReadOnlyTest(unittest.TestCase):

    def setUp(self):
        self.test_server = TestServer()
        client = TestClient(servers={"default": self.test_server},
                            users={"default": [("lasote", "mypass")]})
        client.run("--version")
        client.run("config set general.read_only_cache=True")
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def package(self):
        self.copy("*")
"""
        client.save({"conanfile.py": conanfile,
                     "myheader.h": "my header"})
        client.run("create . Pkg/0.1@lasote/channel")
        self.client = client

    def test_basic(self):
        pref = PackageReference(ConanFileReference.loads("Pkg/0.1@lasote/channel"),
                                NO_SETTINGS_PACKAGE_ID)
        path = os.path.join(self.client.cache.package_layout(pref.ref).package(pref), "myheader.h")
        with self.assertRaises(IOError):
            save(path, "Bye World")
        os.chmod(path, 0o777)
        save(path, "Bye World")

    def test_remove(self):
        self.client.run("search")
        self.assertIn("Pkg/0.1@lasote/channel", self.client.out)
        self.client.run("remove Pkg* -f")
        self.assertNotIn("Pkg/0.1@lasote/channel", self.client.out)

    def test_upload(self):
        self.client.run("upload * --all --confirm")
        self.client.run("remove Pkg* -f")
        self.client.run("install Pkg/0.1@lasote/channel")
        self.test_basic()

    def test_upload_change(self):
        self.client.run("upload * --all --confirm")
        client = TestClient(servers={"default": self.test_server},
                            users={"default": [("lasote", "mypass")]})
        client.run("install Pkg/0.1@lasote/channel")
        pref = PackageReference(ConanFileReference.loads("Pkg/0.1@lasote/channel"),
                                NO_SETTINGS_PACKAGE_ID)
        path = os.path.join(client.cache.package_layout(pref.ref).package(pref), "myheader.h")
        with self.assertRaises(IOError):
            save(path, "Bye World")
        os.chmod(path, 0o777)
        save(path, "Bye World")
