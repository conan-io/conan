import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from collections import OrderedDict


class MultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.client = TestClient(servers=self.servers, users=self.users)

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
        
        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)
        client2.run("install %s --build=missing" % str(conan_reference))
        client2.run("info %s" % str(conan_reference))
        self.assertIn("remote0=http://", client2.user_io.out)
        
        # Now install it in other machine from remote 1
        servers = self.servers.copy()
        servers.pop("remote0")
        client3 = TestClient(servers=servers, users=self.users)
        client3.run("install %s --build=missing" % str(conan_reference))
        client3.run("info %s" % str(conan_reference))
        self.assertIn("remote1=http://", client3.user_io.out)
        
    def install_from_remotes_test(self):
        for i in range(3):
            conan_reference = ConanFileReference.loads("Hello%d/0.1@lasote/stable" % i)
            files = cpp_hello_conan_files("Hello%d" % i, "0.1")
            files["conanfile.py"] = files["conanfile.py"].replace("def build(", "def build2(")
            self.client.save(files)
            self.client.run("export lasote/stable")
            self.client.run("upload %s -r=remote%d" % (str(conan_reference), i))

            self.client.run("info %s" % str(conan_reference))
            self.assertIn("remote%d=http://" % i, self.client.user_io.out)
        
        
        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)
        conan_reference = ConanFileReference.loads("HelloX/0.1@lasote/stable")
        files = cpp_hello_conan_files("HelloX", "0.1", deps=["Hello0/0.1@lasote/stable",
                                                             "Hello1/0.1@lasote/stable",
                                                             "Hello2/0.1@lasote/stable"])
        files["conanfile.py"] = files["conanfile.py"].replace("def build(", "def build2(")
        client2.save(files)
        client2.run("install --build=missing")
        self.assertIn("Hello0/0.1@lasote/stable from remote0", client2.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable from remote1", client2.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable from remote2", client2.user_io.out)
        client2.run("info")
        self.assertIn("Remote: remote0=http://", client2.user_io.out)
        self.assertIn("Remote: remote1=http://", client2.user_io.out)
        self.assertIn("Remote: remote2=http://", client2.user_io.out)
        
     

        


        