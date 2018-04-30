import unittest
from conans.test.utils.tools import TestClient, TestServer

class PackageIdTest(unittest.TestCase):

    def value_parse_test(self):
        # https://github.com/conan-io/conan/issues/2816
        conanfile = """
from conans import ConanFile

class TestConan(ConanFile):
    name = "test"
    version = "0.1"
    settings = "os", "compiler", "arch", "build_type"
    exports_sources = "header.h"

    def package_id(self):
        self.info.settings.compiler.version = "kk=kk"

    def package(self):
        self.copy("header.h", dst="include", keep_path=True)
"""
        server = TestServer([("*/*@*/*", "*")], [("*/*@*/*", "*")], users={"lasote": "mypass"})
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({"conanfile.py": conanfile,
                     "header.h": "header content"})
        client.run("create . danimtb/testing")
        client.run("search test/0.1@danimtb/testing")
        self.assertIn("compiler.version: kk=kk", client.out)
        client.run("upload test/0.1@danimtb/testing --all")
        client.run("remove test/0.1@danimtb/testing --force")
        client.run("install test/0.1@danimtb/testing")
        client.run("search test/0.1@danimtb/testing")
        self.assertIn("compiler.version: kk=kk", client.out)
