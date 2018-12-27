import json
import time
import unittest
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


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
        self.assertIn(": remote1", self.client.user_io.out)

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
        err = client2.run("install MyLib/0.1@conan/testing --build=missing", assert_error=True)
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

    @unittest.skipIf(TestClient().revisions,
                     "This test is not valid for revisions, where we keep iterating the remotes "
                     "for searching a package for the same recipe revision")
    def package_binary_remote_test(self):
        # https://github.com/conan-io/conan/issues/3882
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        # Upload recipe + package to remote1 and remote2
        ref = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % ref)
        self.client.run("upload %s -r=remote0 --all" % ref)
        self.client.run("upload %s -r=remote2 --all" % ref)

        rev1 = self.client.get_revision(ConanFileReference.loads(ref))

        # Remove only binary from remote1 and everything in local
        self.client.run("remove -f %s -p -r remote0" % ref)
        self.client.run('remove "*" -f')

        self.servers.pop("remote1")
        # Now install it from a client, it won't find the binary in remote2
        self.client.run("install %s" % ref, assert_error=True)
        self.assertIn("Can't find a 'Hello/0.1@lasote/stable' package", self.client.out)
        self.assertNotIn("remote2", self.client.out)

        self.client.run("install %s -r remote2" % ref)
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        self.assertIn("Hello/0.1@lasote/stable from 'remote0' - Cache", self.client.out)
        registry = load(self.client.client_cache.registry_path)
        registry = json.loads(registry)
        self.assertEquals(registry["references"], {"Hello/0.1@lasote/stable": "remote0"})
        self.assertEquals(registry["package_references"],
                          {"Hello/0.1@lasote/stable:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9":
                           "remote2"})

        client2 = TestClient(servers=self.servers, users=self.users)
        time.sleep(1)  # Make sure timestamps increase
        client2.save({"conanfile.py": conanfile + " # Comment"})
        client2.run("create . %s" % ref)
        client2.run("upload %s -r=remote2 --all" % ref)

        # Install from client, it should update the package from remote2
        self.client.run("install %s --update" % ref)

        self.assertNotIn("Hello/0.1@lasote/stable: WARN: Can't update, no package in remote",
                         self.client.out)
        self.assertIn("Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", self.client.out)
        self.assertIn("Downloading conan_package.tgz", self.client.out)

        if not self.client.revisions and not self.client.block_v2:
            self.client.run("install %s#%s --update" % (ref, rev1))

            self.assertIn("Hello/0.1@lasote/stable:"
                          "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Cache", self.client.out)
