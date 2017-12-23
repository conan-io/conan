import unittest
from conans.util.files import mkdir, path_exists
import os
from conans.test.utils.tools import TestServer, TestClient
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.util.files import load
from conans.test.utils.test_files import temp_folder


class PathExistsTest(unittest.TestCase):

    def test_paths(self):
        """Unit test of path_exists"""
        tmp_dir = temp_folder()
        tmp_dir = os.path.join(tmp_dir, "WhatEver")
        new_path = os.path.join(tmp_dir, "CapsDir")
        mkdir(new_path)
        self.assertTrue(path_exists(new_path, tmp_dir))
        self.assertFalse(path_exists(os.path.join(tmp_dir, "capsdir"), tmp_dir))

    def test_conanfile_not_found(self):
        test_server = TestServer()
        self.servers = {"default": test_server}
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})

        files = cpp_hello_conan_files("Hello0", "0.1", build=False)

        self.client.save(files)
        self.client.run("export . lasote/stable")

        self.assertRaises(Exception, self.client.run, "install hello0/0.1@lasote/stable")
        self.client.run("install Hello0/0.1@lasote/stable --build missing")
        self.client.run("upload Hello0/0.1@lasote/stable")

        # Now with requirements.txt (bug in server)
        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self.client.save({"conanfile.txt": "[requires]\nHello0/0.1@lasote/stable\n[generators]\ntxt"})
        self.client.run("install . --build missing ")
        build_info = load(os.path.join(self.client.current_folder, "conanbuildinfo.txt"))
        self.assertIn("helloHello0", build_info)

        self.client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")]})
        self.client.save({"conanfile.txt": "[requires]\nhello0/0.1@lasote/stable\n[generators]\ntxt"})
        self.assertRaises(Exception, self.client.run, "install")
