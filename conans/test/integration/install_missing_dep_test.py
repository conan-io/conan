import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load, save
from time import sleep
import time
from conans.paths import CONAN_MANIFEST


class InstallMissingDependency(unittest.TestCase):

    def missing_dep_test(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        # Create deps packages
        dep1_conanfile = """from conans import ConanFile
class Dep1Pkg(ConanFile):
    name = "dep1"
        """

        dep2_conanfile = """from conans import ConanFile
class Dep2Pkg(ConanFile):
    name = "dep2"
    version = "1.0"
    requires = "dep1/1.0@lasote/testing"
        """

        self.client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        self.client.run("create . dep1/1.0@lasote/testing")
        self.client.run("create . dep1/2.0@lasote/testing")

        self.client.save({"conanfile.py": dep2_conanfile}, clean_first=True)
        self.client.run("create . lasote/testing")

        foo_conanfile = """from conans import ConanFile
class FooPkg(ConanFile):
    name = "foo"
    version = "1.0"
    requires = "dep1/{dep1_version}@lasote/testing", "dep2/1.0@lasote/testing"
        """
        self.client.save({"conanfile.py": foo_conanfile.format(dep1_version="1.0")},
                         clean_first=True)
        error = self.client.run("create . lasote/testing")
        self.assertFalse(error)

        self.client.save({"conanfile.py": foo_conanfile.format(dep1_version="2.0")},
                         clean_first=True)
        error = self.client.run("create . lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Can't find a 'dep2/1.0@lasote/testing' package", self.client.user_io.out)
        self.assertIn("- Dependencies: dep1/2.0@lasote/testing", self.client.user_io.out)

