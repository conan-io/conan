import unittest
from conans.test.utils.tools import TestClient, TestServer


class PackageIdTest(unittest.TestCase):

    def double_package_id_call_test(self):
        # https://github.com/conan-io/conan/issues/3085
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    settings = "os", "arch"

    def package_id(self):
        self.output.info("Calling package_id()")
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing")
        out = str(client.out)
        self.assertEqual(1, out.count("Pkg/0.1@user/testing: Calling package_id()"))

    def remove_option_setting_test(self):
        # https://github.com/conan-io/conan/issues/2826
        conanfile = """from conans import ConanFile

class TestConan(ConanFile):
    settings = "os"
    options = {"opt": [True, False]}
    default_options = "opt=False"

    def package_id(self):
        self.output.info("OPTION OPT=%s" % self.info.options.opt)
        del self.info.settings.os
        del self.info.options.opt
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@user/testing -s os=Windows")
        self.assertIn("Pkg/0.1@user/testing: OPTION OPT=False", client.out)
        self.assertIn("Pkg/0.1@user/testing: Package "
                      "'5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
                      client.out)
        client.run("create . Pkg/0.1@user/testing -s os=Linux -o Pkg:opt=True")
        self.assertIn("Pkg/0.1@user/testing: OPTION OPT=True", client.out)
        self.assertIn("Pkg/0.1@user/testing: Package "
                      "'5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9' created",
                      client.out)

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
