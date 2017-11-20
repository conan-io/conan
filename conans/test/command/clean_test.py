import unittest

from conans.test.utils.tools import TestClient
import os
from conans.model.ref import PackageReference, ConanFileReference


class CleanTest(unittest.TestCase):

    def setUp(self):
        conanfile = '''from conans import ConanFile
class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "*"
    def package(self):
        self.copy("*")
'''
        test_conanfile = '''from conans import ConanFile
class HelloConan(ConanFile):
    def test(self):
        pass
'''
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "header.h": "myheader",
                     "test_package/conanfile.py": test_conanfile})
        client.run("create user/channel")
        self.client = client

        self.conan_ref = ConanFileReference.loads("Hello/0.1@user/channel")
        self.pkg_ref = PackageReference(self.conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package/build")))
        self.assertTrue(os.path.exists(client.client_cache.export(self.conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.source(self.conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.export_sources(self.conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.build(self.pkg_ref)))
        self.assertTrue(os.path.exists(client.client_cache.package(self.pkg_ref)))

    def test_clean(self):
        for _ in (1, 2):
            self.client.run("clean . cache")
            self.assertFalse(os.path.exists(os.path.join(self.client.current_folder, "test_package/build")))
            self.assertTrue(os.path.exists(self.client.client_cache.export(self.conan_ref)))
            self.assertFalse(os.path.exists(self.client.client_cache.source(self.conan_ref)))
            self.assertTrue(os.path.exists(self.client.client_cache.export_sources(self.conan_ref)))
            self.assertFalse(os.path.exists(self.client.client_cache.build(self.pkg_ref)))
            self.assertTrue(os.path.exists(self.client.client_cache.package(self.pkg_ref)))

    def test_cache(self):
        self.client.run("clean  cache")
        self.assertTrue(os.path.exists(os.path.join(self.client.current_folder, "test_package/build")))
        self.assertFalse(os.path.exists(self.client.client_cache.source(self.conan_ref)))
        self.assertFalse(os.path.exists(self.client.client_cache.build(self.pkg_ref)))

    def test_local(self):
        self.client.run("clean  .")
        self.assertFalse(os.path.exists(os.path.join(self.client.current_folder, "test_package/build")))
        self.assertTrue(os.path.exists(self.client.client_cache.source(self.conan_ref)))
        self.assertTrue(os.path.exists(self.client.client_cache.export_sources(self.conan_ref)))
        self.assertTrue(os.path.exists(self.client.client_cache.build(self.pkg_ref)))

    def test_error(self):
        # too few arguments
        error = self.client.run("clean", ignore_error=True)
        self.assertTrue(error)
