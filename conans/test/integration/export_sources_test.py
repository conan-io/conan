import unittest
from conans.test.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.paths import EXPORT_SOURCES_DIR, EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME

conanfile_py = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    exports_sources = "*.h", "*.cpp"
    def package(self):
        self.copy("*.h", "include")
"""
hello = """
#pragma once
#include <iostream>
void hello(){std::cout<<"Hello World!";}
"""

conanfile = """[requires]
Hello/0.1@lasote/testing
"""


class ExportsSourcesTest(unittest.TestCase):

    def export_test(self):
        test_server = TestServer()
        servers = {"default": test_server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})

        client.save({"conanfile.py": conanfile_py,
                     "hello.h": hello})
        client.run("export lasote/testing")
        ref = ConanFileReference.loads("Hello/0.1@lasote/testing")
        export = client.client_cache.export(ref)
        export_sources = os.path.join(export, EXPORT_SOURCES_DIR)
        self.assertEqual(sorted(os.listdir(export)),
                         sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanmanifest.txt']))
        self.assertEqual(os.listdir(export_sources), ["hello.h"])

        # now build package
        client.run("install Hello/0.1@lasote/testing --build=missing")
        source_folder = client.client_cache.source(ref)
        self.assertEqual(sorted(os.listdir(source_folder)),
                         sorted(['conanfile.py', 'conanfile.pyc', 'conanmanifest.txt', "hello.h"]))
        package_ref = PackageReference(ref, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.client_cache.package(package_ref)
        include_folder = os.path.join(package_folder, "include")
        self.assertEqual(os.listdir(include_folder), ["hello.h"])

        # upload to remote
        client.run("upload Hello/0.1@lasote/testing --all")
        self.assertEqual(sorted(os.listdir(export)),
                         sorted([EXPORT_SOURCES_DIR, 'conanfile.py', 'conanfile.pyc',
                                 'conanmanifest.txt',
                                 EXPORT_SOURCES_TGZ_NAME,
                                 EXPORT_TGZ_NAME]))
        self.assertEqual(os.listdir(export_sources), ["hello.h"])

        # remove local
        client.run('remove Hello/0.1@lasote/testing -f')

        # install from remote
        client.run("install Hello/0.1@lasote/testing")
        self.assertEqual(sorted(os.listdir(export)),
                         sorted(['conanfile.py', 'conanfile.pyc', 'conanmanifest.txt']))
        self.assertEqual(os.listdir(include_folder), ["hello.h"])






