import time
import unittest
from collections import OrderedDict
from time import sleep

import pytest

from conans.model.ref import ConanFileReference
from conans.paths import CONANFILE
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.env_reader import get_env


class ExportsSourcesMissingTest(unittest.TestCase):

    def test_exports_sources_missing(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("create . pkg/0.1@user/testing")
        client.run("upload pkg/0.1@user/testing --all")

        # Failure because remote is removed
        servers = OrderedDict(client.servers)
        servers["new_server"] = TestServer(users={"user": "password"})
        client2 = TestClient(servers=servers, users={"new_server": [("user", "password")]})
        client2.run("install pkg/0.1@user/testing")
        client2.run("remote remove default")
        client2.run("upload pkg/0.1@user/testing --all -r=new_server", assert_error=True)
        self.assertIn("The 'pkg/0.1@user/testing' package has 'exports_sources' but sources "
                      "not found in local cache.", client2.out)
        self.assertIn("Probably it was installed from a remote that is no longer available.",
                      client2.out)

        # Failure because remote removed the package
        client2 = TestClient(servers=servers, users={"new_server": [("user", "password")],
                                                     "default":  [("user", "password")]})
        client2.run("install pkg/0.1@user/testing")
        client2.run("remove * -r=default -f")
        client2.run("upload pkg/0.1@user/testing --all -r=new_server", assert_error=True)
        self.assertIn("ERROR: pkg/0.1@user/testing: Upload recipe to 'new_server' failed: "
                      "Recipe not found: 'pkg/0.1@user/testing'. [Remote: default]",
                      client2.out)
        self.assertIn("The 'pkg/0.1@user/testing' package has 'exports_sources' but sources "
                      "not found in local cache.", client2.out)
        self.assertIn("Probably it was installed from a remote that is no longer available.",
                      client2.out)


class MultiRemotesTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.servers["default"] = TestServer()
        self.servers["local"] = TestServer()

    def test_list_ref_no_remote(self):
        client = TestClient(servers=self.servers)
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . pkg/1.0@")
        client.run("remote list_ref")
        self.assertNotIn("pkg", client.out)
        client.run("remote list_pref pkg/1.0@")
        self.assertNotIn("pkg", client.out)
        client.run("remote list_ref --no-remote")
        self.assertIn("pkg/1.0: None", client.out)
        client.run("remote list_pref pkg/1.0 --no-remote")
        self.assertIn("pkg/1.0:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9: None", client.out)

    @staticmethod
    def _create(client, number, version, modifier=""):
        files = {CONANFILE: str(GenConanfile(number, version)) + modifier}
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")

    def test_conan_install_build_flag(self):
        """
        Checks conan install --update works with different remotes and changes the associated ones
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

    def test_conan_install_update(self):
        """
        Checks conan install --update works only with the remote associated
        """
        client = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                         "local": [("lasote", "mypass")]})

        self._create(client, "Hello0", "0.0")
        client.run("install Hello0/0.0@lasote/stable --build missing")
        client.run("upload Hello0/0.0@lasote/stable --all -r default")
        sleep(1)  # For timestamp and updates checks
        self._create(client, "Hello0", "0.0", modifier=" ")
        client.run("install Hello0/0.0@lasote/stable --build missing")
        client.run("upload Hello0/0.0@lasote/stable --all -r local")
        client.run("remove '*' -f")

        client.run("install Hello0/0.0@lasote/stable")
        self.assertIn("Hello0/0.0@lasote/stable from 'default' - Downloaded", client.out)
        client.run("install Hello0/0.0@lasote/stable --update")
        self.assertIn("Hello0/0.0@lasote/stable from 'default' - Cache", client.out)

        # Check that it really updates from the indicated remote
        client.run("install Hello0/0.0@lasote/stable --update -r local")
        self.assertIn("Hello0/0.0@lasote/stable from 'local' - Updated", client.out)

        sleep(1)  # For timestamp and updates checks
        # Check that it really updates in case of newer package uploaded to the associated remote
        client_b = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                           "local": [("lasote", "mypass")]})
        self._create(client_b, "Hello0", "0.0", modifier="  ")
        client_b.run("install Hello0/0.0@lasote/stable --build missing")
        client_b.run("upload Hello0/0.0@lasote/stable --all -r local")
        client.run("install Hello0/0.0@lasote/stable --update")
        self.assertIn("Hello0/0.0@lasote/stable from 'local' - Updated", client.out)


class MultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.client = TestClient(servers=self.servers, users=self.users)

    def test_predefine_remote(self):
        self.client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
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

    def test_upload(self):
        ref = ConanFileReference.loads("Hello0/0.1@lasote/stable")
        self.client.save({"conanfile.py": GenConanfile("Hello0", "0.1")})
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

    def test_fail_when_not_notfound(self):
        """
        If a remote fails with a 404 it has to keep looking in the next remote, but if it fails by
        any other reason it has to stop
        """
        servers = OrderedDict()
        servers["s0"] = TestServer()
        servers["s1"] = TestServer()
        servers["s2"] = TestServer()

        client = TestClient(servers=servers, users=self.users)
        client.save({"conanfile.py": GenConanfile("MyLib", "0.1")})
        client.run("create . lasote/testing")
        client.run("user lasote -p mypass -r s1")
        client.run("upload MyLib* -r s1 -c")

        servers["s1"].fake_url = "http://asdlhaljksdhlajkshdljakhsd.com"  # Do not exist
        client2 = TestClient(servers=servers, users=self.users)
        err = client2.run("install MyLib/0.1@conan/testing --build=missing", assert_error=True)
        self.assertTrue(err)
        self.assertIn("MyLib/0.1@conan/testing: Trying with 's0'...", client2.out)
        self.assertIn("MyLib/0.1@conan/testing: Trying with 's1'...", client2.out)
        self.assertIn("Unable to connect to s1=http://asdlhaljksdhlajkshdljakhsd.com", client2.out)
        # s2 is not even tried
        self.assertNotIn("MyLib/0.1@conan/testing: Trying with 's2'...", client2.out)

    def test_install_from_remotes(self):
        for i in range(3):
            ref = ConanFileReference.loads("Hello%d/0.1@lasote/stable" % i)
            self.client.save({"conanfile.py": GenConanfile("Hello%d" % i, "0.1")})
            self.client.run("export . lasote/stable")
            self.client.run("upload %s -r=remote%d" % (str(ref), i))

            self.client.run("info %s" % str(ref))
            self.assertIn("remote%d=http://" % i, self.client.out)

        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers, users=self.users)

        refs = ["Hello0/0.1@lasote/stable", "Hello1/0.1@lasote/stable", "Hello2/0.1@lasote/stable"]
        client2.save({"conanfile.py": GenConanfile("HelloX", "0.1").with_requires(*refs)})
        client2.run("install . --build=missing")
        self.assertIn("Hello0/0.1@lasote/stable from 'remote0'", client2.out)
        self.assertIn("Hello1/0.1@lasote/stable from 'remote1'", client2.out)
        self.assertIn("Hello2/0.1@lasote/stable from 'remote2'", client2.out)
        client2.run("info .")
        self.assertIn("Remote: remote0=http://", client2.out)
        self.assertIn("Remote: remote1=http://", client2.out)
        self.assertIn("Remote: remote2=http://", client2.out)

    @pytest.mark.skipif(get_env("TESTING_REVISIONS_ENABLED", False),
                        reason="This test is not valid for revisions, where we keep iterating the "
                               "remotes for searching a package for the same recipe revision")
    def test_package_binary_remote(self):
        # https://github.com/conan-io/conan/issues/3882
        # Upload recipe + package to remote1 and remote2
        reference = "Hello/0.1@lasote/stable"
        self.client.save({"conanfile.py": GenConanfile()})
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
        client2.save({"conanfile.py": str(GenConanfile()) + " # Comment"})
        client2.run("create . %s" % reference)
        client2.run("upload %s -r=remote2 --all" % reference)

        # Install from client, it should update the package from remote2
        self.client.run("install %s --update" % reference)

        self.assertNotIn("Hello/0.1@lasote/stable: WARN: Can't update, no package in remote",
                         self.client.out)
        self.assertIn("Hello/0.1@lasote/stable:"
                      "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9 - Update", self.client.out)
        self.assertIn("Downloading conan_package.tgz", self.client.out)
