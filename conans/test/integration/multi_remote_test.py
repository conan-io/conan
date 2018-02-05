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

    def predefine_remote_test(self):
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("upload Hello0/0.1@lasote/stable -r=remote0")
        self.client.run("upload Hello0/0.1@lasote/stable -r=remote1")
        self.client.run("upload Hello0/0.1@lasote/stable -r=remote2")
        self.client.run('remove "*" -f')
        self.client.run("remote add_ref Hello0/0.1@lasote/stable remote1")
        self.client.run("install Hello0/0.1@lasote/stable --build=missing")
        self.assertIn("Hello0/0.1@lasote/stable: Retrieving from predefined remote 'remote1'",
                      self.client.user_io.out)
        self.client.run("remote list_ref")
        self.assertIn("Hello0/0.1@lasote/stable: remote1", self.client.user_io.out)

    def upload_test(self):
        conan_reference = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export . lasote/stable")
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

    def fail_when_not_notfound_test(self):
        """
        If a remote fails with a 404 it has to keep looking in the next remote, but if it fails by
        any other reason it has to stop
        """
        servers = OrderedDict()
        servers["s0"] = TestServer()
        servers["s1"] = TestServer()
        servers["s2"] = TestServer()

        client = TestClient(servers=servers, users=self.users)
        files = cpp_hello_conan_files("MyLib", "0.1", build=False)
        client.save(files)
        client.run("create . lasote/testing")
        client.run("user lasote -p mypass -r s1")
        client.run("upload MyLib* -r s1 -c")

        servers["s1"].fake_url = "http://asdlhaljksdhlajkshdljakhsd"  # Do not exist
        client2 = TestClient(servers=servers, users=self.users)
        err = client2.run("install MyLib/0.1@conan/testing --build=missing", ignore_error=True)
        self.assertTrue(err)
        self.assertIn("MyLib/0.1@conan/testing: Trying with 's0'...", client2.out)
        self.assertIn("MyLib/0.1@conan/testing: Trying with 's1'...", client2.out)
        self.assertIn("Unable to connect to s1=http://asdlhaljksdhlajkshdljakhsd", client2.out)
        # s2 is not even tried
        self.assertNotIn("MyLib/0.1@conan/testing: Trying with 's2'...", client2.out)

    def install_from_remotes_test(self):
        for i in range(3):
            conan_reference = ConanFileReference.loads("Hello%d/0.1@lasote/stable" % i)
            files = cpp_hello_conan_files("Hello%d" % i, "0.1", build=False)
            self.client.save(files)
            self.client.run("export . lasote/stable")
            self.client.run("upload %s -r=remote%d" % (str(conan_reference), i))

            self.client.run("info %s" % str(conan_reference))
            self.assertIn("remote%d=http://" % i, self.client.user_io.out)

        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)
        files = cpp_hello_conan_files("HelloX", "0.1", deps=["Hello0/0.1@lasote/stable",
                                                             "Hello1/0.1@lasote/stable",
                                                             "Hello2/0.1@lasote/stable"])
        files["conanfile.py"] = files["conanfile.py"].replace("def build(", "def build2(")
        client2.save(files)
        client2.run("install . --build=missing")
        self.assertIn("Hello0/0.1@lasote/stable from 'remote0'", client2.user_io.out)
        self.assertIn("Hello1/0.1@lasote/stable from 'remote1'", client2.user_io.out)
        self.assertIn("Hello2/0.1@lasote/stable from 'remote2'", client2.user_io.out)
        client2.run("info .")
        self.assertIn("Remote: remote0=http://", client2.user_io.out)
        self.assertIn("Remote: remote1=http://", client2.user_io.out)
        self.assertIn("Remote: remote2=http://", client2.user_io.out)
