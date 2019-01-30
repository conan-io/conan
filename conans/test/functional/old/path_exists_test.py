import os
import unittest

from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class PathExistsTest(unittest.TestCase):

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
