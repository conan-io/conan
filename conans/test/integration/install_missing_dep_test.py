import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load, save
from time import sleep
import time
from conans.paths import CONAN_MANIFEST


class InstallMissingDependencie(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"myremote": test_server}
        self.client = TestClient(servers=self.servers, users={"myremote": [("lasote", "mypass")]})

        # Create deps packages
        dep1_conanfile = """from conans import ConanFile
class Dep1Pkg(ConanFile):
    name = "dep1"
    version = "{version}"
        """

        dep2_conanfile = """from conans import ConanFile
class Dep2Pkg(ConanFile):
    name = "dep2"
    version = "1.0"
    requires = "dep1/1.0@lasote/testing"
        """

        self.client.save({"conanfile.py": dep1_conanfile.format(version="1.0")}, clean_first=True)
        self.client.run("create . lasote/testing")

        self.client.save({"conanfile.py": dep1_conanfile.format(version="2.0")}, clean_first=True)
        self.client.run("create . lasote/testing")

        self.client.save({"conanfile.py": dep2_conanfile}, clean_first=True)
        self.client.run("create . lasote/testing")

    def missing_dep_test(self):
        foo_conanfile = """from conans import ConanFile
class FooPkg(ConanFile):
    name = "foo"
    version = "1.0"
    requires = "dep1/{dep1_version}@lasote/testing", "dep2/1.0@lasote/testing"
        """
        self.client.save({"conanfile.py": foo_conanfile.format(dep1_version="1.0")},
                         clean_first=True)
        self.client.run("create . lasote/testing")

        self.client.save({"conanfile.py": foo_conanfile.format(dep1_version="2.0")},
                         clean_first=True)
        self.client.run("create . lasote/testing")

