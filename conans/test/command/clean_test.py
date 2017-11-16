import unittest

from conans.test.utils.tools import TestClient
import os
from conans.model.ref import PackageReference, ConanFileReference


class CleanTest(unittest.TestCase):

    def test_clean(self):
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

        conan_ref = ConanFileReference.loads("Hello/0.1@user/channel")
        pkg_ref = PackageReference(conan_ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertTrue(os.path.exists(os.path.join(client.current_folder, "test_package/build")))
        self.assertTrue(os.path.exists(client.client_cache.export(conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.source(conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.export_sources(conan_ref)))
        self.assertTrue(os.path.exists(client.client_cache.build(pkg_ref)))
        self.assertTrue(os.path.exists(client.client_cache.package(pkg_ref)))

        for _ in (1, 2):
            client.run("clean")
            self.assertFalse(os.path.exists(os.path.join(client.current_folder, "test_package/build")))
            self.assertTrue(os.path.exists(client.client_cache.export(conan_ref)))
            self.assertFalse(os.path.exists(client.client_cache.source(conan_ref)))
            self.assertTrue(os.path.exists(client.client_cache.export_sources(conan_ref)))
            self.assertFalse(os.path.exists(client.client_cache.build(pkg_ref)))
            self.assertTrue(os.path.exists(client.client_cache.package(pkg_ref)))
