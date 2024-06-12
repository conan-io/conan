import unittest
from collections import OrderedDict
from time import sleep

from conans.model.recipe_ref import RecipeReference
from conan.internal.paths import CONANFILE
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer


class ExportsSourcesMissingTest(unittest.TestCase):

    def test_exports_sources_missing(self):
        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("create . --name=pkg --version=0.1 --user=user --channel=testing")
        client.run("upload pkg/0.1@user/testing -r default")

        # Failure because remote is removed
        servers = OrderedDict(client.servers)
        servers["new_server"] = TestServer(users={"user": "password"})
        client2 = TestClient(servers=servers, inputs=["user", "password"])
        client2.run("install --requires=pkg/0.1@user/testing")
        client2.run("remote remove default")
        client2.run("upload pkg/0.1@user/testing -r=new_server", assert_error=True)
        self.assertIn("The 'pkg/0.1@user/testing' package has 'exports_sources' but sources "
                      "not found in local cache.", client2.out)
        self.assertIn("Probably it was installed from a remote that is no longer available.",
                      client2.out)

        # Failure because remote removed the package
        client2 = TestClient(servers=servers, inputs=2*["admin", "password"])
        client2.run("install --requires=pkg/0.1@user/testing")
        client2.run("remove * -r=default -c")
        client2.run("upload pkg/0.1@user/testing -r=new_server", assert_error=True)
        self.assertIn("pkg/0.1@user/testing Error while compressing: The 'pkg/0.1@user/testing' ",
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

    @staticmethod
    def _create(client, number, version, modifier=""):
        files = {CONANFILE: str(GenConanfile(number, version)) + modifier}
        client.save(files, clean_first=True)
        client.run("export . --user=lasote --channel=stable")

    def test_conan_install_build_flag(self):
        """
        Checks conan install --update works with different remotes
        """
        client_a = TestClient(servers=self.servers, inputs=2*["admin", "password"])
        client_b = TestClient(servers=self.servers, inputs=2*["admin", "password"])

        # Upload hello0 to local and default from client_a
        self._create(client_a, "hello0", "0.0")
        client_a.run("upload hello0/0.0@lasote/stable -r local --only-recipe")
        client_a.run("upload hello0/0.0@lasote/stable -r default --only-recipe")
        sleep(1)  # For timestamp and updates checks

        # Download hello0 from local with client_b
        client_b.run("install --requires=hello0/0.0@lasote/stable -r local --build missing")

        # Update hello0 with client_a and reupload
        self._create(client_a, "hello0", "0.0", modifier="\n")
        client_a.run("upload hello0/0.0@lasote/stable -r local --only-recipe")
        self.assertIn("Uploading recipe 'hello0/0.0@lasote/stable", client_a.out)

        # Execute info method in client_b, should advise that there is an update
        client_b.run("graph info --requires=hello0/0.0@lasote/stable --check-updates")
        self.assertIn("recipe: Update available", client_b.out)
        self.assertIn("binary: Cache", client_b.out)

        # Now try to update the package with install -u
        client_b.run("install --requires=hello0/0.0@lasote/stable -u --build='*'")
        self.assertIn("hello0/0.0@lasote/stable#64fd8ae21db9eff69c6c681b0e2fc178 - Updated",
                      client_b.out)

        # Upload a new version from client A, but only to the default server (not the ref-listed)
        # Upload hello0 to local and default from client_a
        sleep(1)  # For timestamp and updates checks
        self._create(client_a, "hello0", "0.0", modifier="\n\n")
        client_a.run("upload hello0/0.0@lasote/stable#latest -r default --only-recipe")

        # Now client_b checks for updates without -r parameter
        # TODO: cache2.0 conan info not yet implemented with new cache
        client_b.run("graph info --requires=hello0/0.0@lasote/stable --check-updates")
        self.assertIn("recipe: Update available", client_b.out)
        # self.assertIn("Recipe: Cache", client_b.out)

        # But if we connect to default, should tell us that there is an update IN DEFAULT!
        # TODO: cache2.0 conan info not yet implemented with new cache
        client_b.run("graph info --requires=hello0/0.0@lasote/stable -r default --check-updates")
        # self.assertIn("Remote: local", client_b.out)
        self.assertIn("recipe: Update available", client_b.out)

        # Well, now try to update the package with -r default -u
        client_b.run("install --requires=hello0/0.0@lasote/stable -r default -u --build='*'")
        self.assertIn("hello0/0.0@lasote/stable: Forced build from source",
                      str(client_b.out))
        # TODO: cache2.0 conan info not yet implemented with new cache
        client_b.run("graph info --requires=hello0/0.0@lasote/stable -u")
        self.assertIn("recipe: Cache", client_b.out)
        self.assertIn("binary: Cache", client_b.out)

    def test_conan_install_update(self):
        """
        Checks conan install --update works only with the remote associated
        """
        client = TestClient(servers=self.servers, inputs=2*["admin", "password"])

        self._create(client, "hello0", "0.0")
        default_remote_rev = client.exported_recipe_revision()
        client.run("install --requires=hello0/0.0@lasote/stable --build missing")

        client.run("upload hello0/0.0@lasote/stable -r default")
        sleep(1)  # For timestamp and updates checks
        self._create(client, "hello0", "0.0", modifier=" ")
        local_remote_rev = client.exported_recipe_revision()
        client.run("install --requires=hello0/0.0@lasote/stable --build missing")

        client.run("upload hello0/0.0@lasote/stable#latest -r local")
        client.run("remove '*' -c")

        client.run("install --requires=hello0/0.0@lasote/stable")
        # If we don't set a remote we find between all remotes and get the first match
        assert f"hello0/0.0@lasote/stable#{default_remote_rev} - Downloaded" in client.out
        client.run("install --requires=hello0/0.0@lasote/stable --update")
        assert f"hello0/0.0@lasote/stable#{local_remote_rev} - Updated" in client.out

        client.run("install --requires=hello0/0.0@lasote/stable --update -r default")
        self.assertIn(f"hello0/0.0@lasote/stable#{local_remote_rev} - Newer",
                      client.out)

        sleep(1)  # For timestamp and updates checks
        # Check that it really updates in case of newer package uploaded to the associated remote
        client_b = TestClient(servers=self.servers, inputs=3*["admin", "password"])
        self._create(client_b, "hello0", "0.0", modifier="  ")
        new_local_remote_rev = client_b.exported_recipe_revision()
        client_b.run("install --requires=hello0/0.0@lasote/stable --build missing")
        client_b.run("upload hello0/0.0@lasote/stable -r local")
        client.run("install --requires=hello0/0.0@lasote/stable --update")
        assert f"hello0/0.0@lasote/stable#{new_local_remote_rev} - Updated" in client.out


class MultiRemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("admin", "password")]

        self.client = TestClient(servers=self.servers, inputs=3*["admin", "password"])

    def test_fail_when_not_notfound(self):
        """
        If a remote fails with a 404 it has to keep looking in the next remote, but if it fails by
        any other reason it has to stop
        """
        servers = OrderedDict()
        servers["s0"] = TestServer()
        servers["s1"] = TestServer()
        servers["s2"] = TestServer()

        client = TestClient(servers=servers)
        client.save({"conanfile.py": GenConanfile("mylib", "0.1")})
        client.run("create . --user=lasote --channel=testing")
        client.run("remote login s1 admin -p password")
        client.run("upload mylib* -r s1 -c")

        servers["s1"].fake_url = "http://asdlhaljksdhlajkshdljakhsd.com"  # Do not exist
        client2 = TestClient(servers=servers)
        client2.run("install --requires=mylib/0.1@conan/testing --build=missing", assert_error=True)
        self.assertIn("mylib/0.1@conan/testing: Checking remote: s0", client2.out)
        self.assertIn("mylib/0.1@conan/testing: Checking remote: s1", client2.out)
        self.assertIn("Unable to connect to remote s1=http://asdlhaljksdhlajkshdljakhsd.com",
                      client2.out)
        # s2 is not even tried
        self.assertNotIn("mylib/0.1@conan/testing: Trying with 's2'...", client2.out)

    def test_install_from_remotes(self):
        for i in range(3):
            ref = RecipeReference.loads("hello%d/0.1@lasote/stable" % i)
            self.client.save({"conanfile.py": GenConanfile("hello%d" % i, "0.1")})
            self.client.run("export . --user=lasote --channel=stable")
            self.client.run("upload %s -r=remote%d" % (str(ref), i))

        # Now install it in other machine from remote 0
        client2 = TestClient(servers=self.servers)

        refs = ["hello0/0.1@lasote/stable", "hello1/0.1@lasote/stable", "hello2/0.1@lasote/stable"]
        client2.save({"conanfile.py": GenConanfile("helloX", "0.1").with_requires(*refs)})
        client2.run("install . --build=missing")
        client2.assert_listed_require({"hello0/0.1@lasote/stable": "Downloaded (remote0)",
                                       "hello1/0.1@lasote/stable": "Downloaded (remote1)",
                                       "hello2/0.1@lasote/stable": "Downloaded (remote2)",
                                       })
