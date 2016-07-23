import unittest
from conans.test.tools import TestClient, TestServer
from conans.model.ref import ConanFileReference, PackageReference
import os
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load
from time import sleep


class InstallUpdateTest(unittest.TestCase):

    def setUp(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

    def reuse_test(self):
        files = cpp_hello_conan_files("Hello0", "1.0", build=False)

        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2 = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        client2.run("install Hello0/1.0@lasote/stable")

        files["helloHello0.h"] = "//EMPTY!"
        self.client.save(files, clean_first=True)
        sleep(1)
        self.client.run("export lasote/stable")
        self.client.run("install Hello0/1.0@lasote/stable --build")
        self.client.run("upload Hello0/1.0@lasote/stable --all")

        client2.run("install Hello0/1.0@lasote/stable --update")
        ref = ConanFileReference.loads("Hello0/1.0@lasote/stable")
        package_ids = client2.paths.conan_packages(ref)
        package_path = client2.paths.package(PackageReference(ref, package_ids[0]))
        header = load(os.path.join(package_path, "include/helloHello0.h"))
        self.assertEqual(header, "//EMPTY!")
