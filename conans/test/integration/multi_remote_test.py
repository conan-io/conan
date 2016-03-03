import unittest
from conans.test.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from collections import OrderedDict


class MultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        users = {}
        for i in range(3):
            test_server = TestServer([("*/*@*/*", "*")],  # read permissions
                                     [],  # write permissions
                                     users={"lasote": "mypass"})  # exported users and passwords
            self.servers["remote%d" % i] = test_server
            users["remote%d" % i] = [("lasote", "mypass")]
           
        self.client = TestClient(servers=self.servers, users=users)

    def upload_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1")
        files["conanfile.py"] = files["conanfile.py"].replace("def build(", "def build2(")
        self.client.save(files)
        self.client.run("export lasote/stable")
        self.client.run("upload %s" % str(conan_reference))
        
        self.client.run("info %s" % str(conan_reference))
        self.assertIn("remote0=http://", self.client.user_io.out)
        
        # The remote, once fixed does not change
        self.client.run("upload %s -r=remote1" % str(conan_reference))   
        self.client.run("info %s" % str(conan_reference))
        self.assertIn("remote0=http://", self.client.user_io.out)

        