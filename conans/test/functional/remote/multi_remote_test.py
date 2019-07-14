import time
import unittest
from collections import OrderedDict
from time import sleep

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from conans.test.utils.tools import TestClient, TestServer


class MultiRemotesTest(unittest.TestCase):

    def setUp(self):
        default_server = TestServer()
        local_server = TestServer()
        self.servers = OrderedDict()
        self.servers["default"] = default_server
        self.servers["local"] = local_server

    def _create(self, client, number, version, deps=None, export=True, modifier=""):
        files = cpp_hello_conan_files(number, version, deps, build=False)
        # To avoid building
        files = {CONANFILE: files[CONANFILE].replace("config(", "config2(") + modifier}
        client.save(files, clean_first=True)
        if export:
            client.run("export . lasote/stable")

    def conan_install_build_flag_test(self):
        """
        Checks conan install --update works with different remotes and changes the asociated ones
        in registry accordingly
        """
        client_a = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                           "local": [("lasote", "mypass")]})
        client_b = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                           "local": [("lasote", "mypass")]})

        # Upload Hello0 to local and default from client_a
        self._create(client_a, "Hello0", "0.0")
        client_a.run("upload Hello0/0.0@lasote/stable -r local")
        client_a.run("upload Hello0/0.0@lasote/stable -r default")
        client_a.run("remote list_ref")
        self.assertIn(": local", str(client_a.out))
        sleep(1)  # For timestamp and updates checks

        # Download Hello0 from local with client_b
        client_b.run("install Hello0/0.0@lasote/stable -r local --build missing")
        client_b.run("remote list_ref")
        self.assertIn(": local", str(client_b.out))

        # Update Hello0 with client_a and reupload
        self._create(client_a, "Hello0", "0.0", modifier="\n")
        client_a.run("upload Hello0/0.0@lasote/stable -r local")
        self.assertIn("Uploaded conan recipe 'Hello0/0.0@lasote/stable' to 'local'", client_a.out)

        # Execute info method in client_b, should advise that there is an update
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Recipe: Update available", client_b.out)
        self.assertIn("Binary: Cache", client_b.out)

        # Now try to update the package with install -u
        client_b.run("remote list_ref")
        self.assertIn(": local", str(client_b.out))
        client_b.run("install Hello0/0.0@lasote/stable -u --build")
        self.assertIn("Hello0/0.0@lasote/stable from 'local' - Updated", client_b.out)
        client_b.run("remote list_ref")
        self.assertIn(": local", str(client_b.out))

        # Upload a new version from client A, but only to the default server (not the ref-listed)
        # Upload Hello0 to local and default from client_a
        sleep(1)  # For timestamp and updates checks
        self._create(client_a, "Hello0", "0.0", modifier="\n\n")
        client_a.run("upload Hello0/0.0@lasote/stable -r default")

        # Now client_b checks for updates without -r parameter
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Remote: local", client_b.out)
        self.assertIn("Recipe: Cache", client_b.out)

        # But if we connect to default, should tell us that there is an update IN DEFAULT!
        client_b.run("info Hello0/0.0@lasote/stable -r default -u")
        self.assertIn("Remote: local", client_b.out)
        self.assertIn("Recipe: Update available", client_b.out)
        client_b.run("remote list_ref")
        self.assertIn(": local", str(client_b.out))

        # Well, now try to update the package with -r default -u
        client_b.run("install Hello0/0.0@lasote/stable -r default -u --build")
        self.assertIn("Hello0/0.0@lasote/stable: Calling build()",
                      str(client_b.out))
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Recipe: Cache", client_b.out)
        self.assertIn("Binary: Cache", client_b.out)
        client_b.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: default", client_b.out)


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
                      self.client.out)
        self.client.run("remote list_ref")
        self.assertIn(": remote1", self.client.out)

    def upload_test(self):
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)
        self.client.save(files)
        self.client.run("export . lasote/stable")
        self.client.run("upload %s" % str(ref))

        self.client.run("info %s" % str(ref))
        self.assertIn("remote0=http://", self.client.out)

        # The remote, once fixed does not change
        self.client.run("upload %s -r=remote1" % str(ref))
        self.client.run("info %s" % str(ref))
        self.assertIn("remote0=http://", self.client.out)

        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)
        client2.run("install %s --build=missing" % str(ref))
        client2.run("info %s" % str(ref))
        self.assertIn("remote0=http://", client2.out)

        # Now install it in other machine from remote 1
        servers = self.servers.copy()
        servers.pop("remote0")
        client3 = TestClient(servers=servers, users=self.users)
        client3.run("install %s --build=missing" % str(ref))
        client3.run("info %s" % str(ref))
        self.assertIn("remote1=http://", client3.out)

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
            ref = ConanFileReference.loads("Hello%d/0.1@lasote/stable" % i)
            files = cpp_hello_conan_files("Hello%d" % i, "0.1", build=False)
            self.client.save(files)
            self.client.run("export . lasote/stable")
            self.client.run("upload %s -r=remote%d" % (str(ref), i))

            self.client.run("info %s" % str(ref))
            self.assertIn("remote%d=http://" % i, self.client.out)

        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)
        files = cpp_hello_conan_files("HelloX", "0.1", deps=["Hello0/0.1@lasote/stable",
                                                             "Hello1/0.1@lasote/stable",
                                                             "Hello2/0.1@lasote/stable"])
        files["conanfile.py"] = files["conanfile.py"].replace("def build(", "def build2(")
        client2.save(files)
        client2.run("install . --build=missing")
        self.assertIn("Hello0/0.1@lasote/stable from 'remote0'", client2.out)
        self.assertIn("Hello1/0.1@lasote/stable from 'remote1'", client2.out)
        self.assertIn("Hello2/0.1@lasote/stable from 'remote2'", client2.out)
        client2.run("info .")
        self.assertIn("Remote: remote0=http://", client2.out)
        self.assertIn("Remote: remote1=http://", client2.out)
        self.assertIn("Remote: remote2=http://", client2.out)

    @unittest.skipIf(TestClient().cache.config.revisions_enabled,
                     "This test is not valid for revisions, where we keep iterating the remotes "
                     "for searching a package for the same recipe revision")
    def package_binary_remote_test(self):
        # https://github.com/conan-io/conan/issues/3882
        conanfile = """from conans import ConanFile
class ConanFileToolsTest(ConanFile):
    pass
"""
        # Upload recipe + package to remote1 and remote2
        reference = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": conanfile})
        self.client.run("create . %s" % reference)
        self.client.run("upload %s -r=remote0 --all" % reference)
        self.client.run("upload %s -r=remote2 --all" % reference)
        ref = ConanFileReference.loads(reference)

        # Remove only binary from remote1 and everything in local
        self.client.run("remove -f %s -p -r remote0" % reference)
        self.client.run('remove "*" -f')

        self.servers.pop("remote1")
        # Now install it from a client, it won't find the binary in remote2
        self.client.run("install %s" % reference, assert_error=True)
        self.assertIn("Can't find a 'Hello/0.1@lasote/stable' package", self.client.out)
        self.assertNotIn("remote2", self.client.out)

        self.client.run("install %s -r remote2" % reference)
        self.assertIn("Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", self.client.out)
        self.assertIn("Hello/0.1@lasote/stable from 'remote0' - Cache", self.client.out)

        metadata = self.client.cache.package_layout(ref).load_metadata()
        self.assertEqual(metadata.recipe.remote, "remote0")
        self.assertEqual(metadata.packages["5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"].remote,
                         "remote2")

        client2 = TestClient(servers=self.servers, users=self.users)
        time.sleep(1)  # Make sure timestamps increase
        client2.save({"conanfile.py": conanfile + " # Comment"})
        client2.run("create . %s" % reference)
        client2.run("upload %s -r=remote2 --all" % reference)

        # Install from client, it should update the package from remote2
        self.client.run("install %s --update" % reference)

        self.assertNotIn("Hello/0.1@lasote/stable: WARN: Can't update, no package in remote",
                         self.client.out)
        self.assertIn("Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", self.client.out)
        self.assertIn("Downloading conan_package.tgz", self.client.out)
