import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import load, save
import os
from conans.model.ref import ConanFileReference, PackageReference


class ReadOnlyTest(unittest.TestCase):

    def setUp(self):
        client = TestClient()
        client.run("--version")
        conf_path = client.client_cache.conan_conf_path
        conf = load(conf_path)
        conf = conf.replace("# read_only_cache = True ", "read_only_cache = True ")
        save(conf_path, conf)
        conanfile = """from conans import ConanFile
class MyPkg(ConanFile):
    exports_sources = "*.h"
    def package(self):
        self.copy("*")
"""
        client.save({"conanfile.py": conanfile,
                     "myheader.h": "my header"})
        client.run("create Pkg/0.1@user/channel")
        self.client = client

    def basic_test(self):
        ref = PackageReference(ConanFileReference.loads("Pkg/0.1@user/channel"),
                               "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        path = os.path.join(self.client.client_cache.package(ref), "myheader.h")
        with self.assertRaises(IOError):
            save(path, "Bye World")
        os.chmod(path, 0o777)
        save(path, "Bye World")

    def remove_test(self):
        self.client.run("search")
        self.assertIn("Pkg/0.1@user/channel", self.client.out)
        self.client.run("remove Pkg* -f")
        self.assertNotIn("Pkg/0.1@user/channel", self.client.out)