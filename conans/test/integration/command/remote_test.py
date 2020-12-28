import json
import re
import unittest
from collections import OrderedDict

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.files import load


class RemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.client = TestClient(servers=self.servers, users=self.users)

    def test_removed_references(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . lib/1.0@lasote/channel")
        self.client.run('upload "*" -c -r remote1')
        self.client.run('upload "*" -c -r remote2')

        self.client.run('remote list_ref')
        ref = "lib/1.0@lasote/channel"
        pref = "%s:%s" % (ref, NO_SETTINGS_PACKAGE_ID)
        self.assertIn("%s: remote1" % ref, self.client.out)

        # Remove from remote2, the reference should be kept there
        self.client.run('remove "lib/1.0@lasote/channel" -f -r remote2')
        self.client.run('remote list_ref')
        self.assertIn("%s: remote1" % ref, self.client.out)

        # Upload again to remote2 and remove from remote1, the ref shouldn't be removed
        self.client.run('upload "*" -c -r remote2')
        self.client.run('remove "lib/1.0@lasote/channel" -f -r remote1')
        self.client.run('remote list_ref')
        self.assertIn("%s: remote1" % ref, self.client.out)

        # Test the packages references now
        self.client.run('upload "*" -c -r remote1 --all')
        self.client.run('upload "*" -c -r remote2 --all')
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertIn("%s: remote1" % pref, self.client.out)

        # Remove from remote2, the reference should be kept there
        self.client.run('remove "lib/1.0@lasote/channel" '
                        '-p %s -f -r remote2' % NO_SETTINGS_PACKAGE_ID)
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertIn("%s: remote1" % pref, self.client.out)

        # Upload again to remote2 and remove from remote1, the ref shouldn't be removed
        self.client.run('upload "*" -c -r remote2 --all')
        self.client.run('remove "lib/1.0@lasote/channel" '
                        '-p %s -f -r remote1' % NO_SETTINGS_PACKAGE_ID)
        self.client.run('remote list_ref')
        self.assertIn("%s: remote1" % ref, self.client.out)
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertIn("%s: remote1" % pref, self.client.out)

        # Remove package locally
        self.client.run('upload "*" -c -r remote1 --all')
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertIn("%s: remote1" % pref, self.client.out)
        self.client.run('remove "lib/1.0@lasote/channel" '
                        '-p %s -f' % NO_SETTINGS_PACKAGE_ID)
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertNotIn("%s: remote1" % pref, self.client.out)

        # If I remove all in local, I also remove packages
        self.client.run("create . lib/1.0@lasote/channel")
        self.client.run('upload "*" -c -r remote1')
        self.client.run('remove "lib/1.0@lasote/channel" -f')
        self.client.run('remote list_pref lib/1.0@lasote/channel')
        self.assertEqual("", self.client.out)

    def test_list_raw(self):
        self.client.run("remote list --raw")
        output = re.sub(r"http://fake.+.com", "http://fake.com", str(self.client.out))
        self.assertIn("remote0 http://fake.com True", output)
        self.assertIn("remote1 http://fake.com True", output)
        self.assertIn("remote2 http://fake.com True", output)

    def test_basic(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.out)
        self.assertIn("remote1: http://", self.client.out)
        self.assertIn("remote2: http://", self.client.out)

        self.client.run("remote add origin https://myurl")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        self.assertIn("origin: https://myurl", lines[3])

        self.client.run("remote update origin https://2myurl")
        self.client.run("remote list")
        self.assertIn("origin: https://2myurl", self.client.out)

        self.client.run("remote update remote0 https://remote0url")
        self.client.run("remote list")
        output = str(self.client.out)
        self.assertIn("remote0: https://remote0url", output.splitlines()[0])

        self.client.run("remote remove remote0")
        self.client.run("remote list")
        output = str(self.client.out)
        self.assertIn("remote1: http://", output.splitlines()[0])

    def test_remove_remote(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.out)
        self.assertIn("remote1: http://", self.client.out)
        self.assertIn("remote2: http://", self.client.out)
        self.client.run("remote add_ref Hello/0.1@user/testing remote2")
        self.client.run("remote add_ref Hello2/0.1@user/testing remote1")
        self.client.run("remote remove remote1")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertIn("remote0", self.client.out)
        self.assertIn("remote2", self.client.out)
        self.client.run("remote list_ref")
        self.assertNotIn("Hello2/0.1@user/testing", self.client.out)
        self.assertIn("Hello/0.1@user/testing", self.client.out)
        registry = load(self.client.cache.remotes_path)
        self.assertNotIn("Hello2/0.1@user/testing", registry)
        ref = ConanFileReference.loads("Hello/0.1@user/testing")
        metadata = self.client.cache.package_layout(ref).load_metadata()
        self.assertEqual(metadata.recipe.remote, "remote2")

        self.client.run("remote remove remote2")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertIn("remote0", self.client.out)
        self.assertNotIn("remote2", self.client.out)
        self.client.run("remote list_ref")
        self.assertNotIn("Hello2/0.1@user/testing", self.client.out)
        self.assertNotIn("Hello/0.1@user/testing", self.client.out)
        registry = load(self.client.cache.remotes_path)
        self.assertNotIn("Hello2/0.1@user/testing", registry)
        self.assertNotIn("Hello/0.1@user/testing", registry)

    def test_clean_remote(self):
        self.client.run("remote add_ref Hello/0.1@user/testing remote0")
        self.client.run("remote clean")
        self.client.run("remote list")
        self.assertEqual("", self.client.out)
        self.client.run("remote list_ref")
        self.assertEqual("", self.client.out)

    def test_clean_remote_no_user(self):
        self.client.run("remote add_ref Hello/0.1 remote0")
        self.client.run("remote clean")
        self.client.run("remote list")
        self.assertEqual("", self.client.out)
        self.client.run("remote list_ref")
        self.assertEqual("", self.client.out)

    def test_remove_remote_no_user(self):
        self.client.run("remote add_ref Hello/0.1 remote0")
        self.client.run("remote remove remote0")
        self.client.run("remote list")
        self.assertNotIn("remote0", self.client.out)
        self.client.run("remote list_ref")
        self.assertEqual("", self.client.out)

    def test_add_force(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote add_ref Hello/0.1@user/testing r2")
        client.run("remote add_ref Hello2/0.1@user/testing r1")

        client.run("remote add r4 https://r4 -f")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r2: https://r2", lines[1])
        self.assertIn("r3: https://r3", lines[2])
        self.assertIn("r4: https://r4", lines[3])

        client.run("remote add r2 https://newr2 -f")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r4: https://r4", lines[2])
        self.assertIn("r2: https://newr2", lines[3])

        client.run("remote add newr1 https://r1 -f")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r3: https://r3", lines[0])
        self.assertIn("r4: https://r4", lines[1])
        self.assertIn("r2: https://newr2", lines[2])
        self.assertIn("newr1: https://r1", lines[3])
        client.run("remote list_ref")
        self.assertIn("Hello2/0.1@user/testing: newr1", client.out)
        self.assertIn("Hello/0.1@user/testing: r2", client.out)

        client.run("remote add newr1 https://newr1 -f -i")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("newr1: https://newr1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r4: https://r4", lines[2])
        self.assertIn("r2: https://newr2", lines[3])

    def test_rename(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote add_ref Hello/0.1@user/testing r2")
        client.run("remote rename r2 mynewr2")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("mynewr2: https://r2", lines[1])
        self.assertIn("r3: https://r3", lines[2])
        client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: mynewr2", client.out)

        # Rename to an existing one
        client.run("remote rename r2 r1", assert_error=True)
        self.assertIn("Remote 'r1' already exists", client.out)

    def test_insert(self):
        self.client.run("remote add origin https://myurl --insert")
        self.client.run("remote list")
        first_line = str(self.client.out).splitlines()[0]
        self.assertIn("origin: https://myurl", first_line)

        self.client.run("remote add origin2 https://myurl2 --insert=0")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        self.assertIn("origin2: https://myurl2", lines[0])
        self.assertIn("origin: https://myurl", lines[1])

        self.client.run("remote add origin3 https://myurl3 --insert=1")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        self.assertIn("origin2: https://myurl2", lines[0])
        self.assertIn("origin3: https://myurl3", lines[1])
        self.assertIn("origin: https://myurl", lines[2])

    def test_update_insert(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")

        client.run("remote update r2 https://r2new --insert")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r2: https://r2new", lines[0])
        self.assertIn("r1: https://r1", lines[1])
        self.assertIn("r3: https://r3", lines[2])

        client.run("remote update r2 https://r2new2 --insert 2")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r2: https://r2new2", lines[2])

    def test_update_insert_same_url(self):
        # https://github.com/conan-io/conan/issues/5107
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote update r2 https://r2 --insert=0")
        client.run("remote list")
        self.assertLess(str(client.out).find("r2"), str(client.out).find("r1"))
        self.assertLess(str(client.out).find("r1"), str(client.out).find("r3"))

    def test_verify_ssl(self):
        client = TestClient()
        client.run("remote add my-remote http://someurl TRUE")
        client.run("remote add my-remote2 http://someurl2 yes")
        client.run("remote add my-remote3 http://someurl3 FALse")
        client.run("remote add my-remote4 http://someurl4 No")
        registry = load(client.cache.remotes_path)
        data = json.loads(registry)
        self.assertEqual(data["remotes"][0]["name"], "my-remote")
        self.assertEqual(data["remotes"][0]["url"], "http://someurl")
        self.assertEqual(data["remotes"][0]["verify_ssl"], True)

        self.assertEqual(data["remotes"][1]["name"], "my-remote2")
        self.assertEqual(data["remotes"][1]["url"], "http://someurl2")
        self.assertEqual(data["remotes"][1]["verify_ssl"], True)

        self.assertEqual(data["remotes"][2]["name"], "my-remote3")
        self.assertEqual(data["remotes"][2]["url"], "http://someurl3")
        self.assertEqual(data["remotes"][2]["verify_ssl"], False)

        self.assertEqual(data["remotes"][3]["name"], "my-remote4")
        self.assertEqual(data["remotes"][3]["url"], "http://someurl4")
        self.assertEqual(data["remotes"][3]["verify_ssl"], False)

    def test_remote_disable(self):
        client = TestClient()
        client.run("remote add my-remote0 http://someurl0")
        client.run("remote add my-remote1 http://someurl1")
        client.run("remote add my-remote2 http://someurl2")
        client.run("remote add my-remote3 http://someurl3")
        client.run("remote disable my-remote0")
        client.run("remote disable my-remote3")
        registry = load(client.cache.remotes_path)
        data = json.loads(registry)
        self.assertEqual(data["remotes"][0]["name"], "my-remote0")
        self.assertEqual(data["remotes"][0]["url"], "http://someurl0")
        self.assertEqual(data["remotes"][0]["disabled"], True)
        self.assertEqual(data["remotes"][3]["name"], "my-remote3")
        self.assertEqual(data["remotes"][3]["url"], "http://someurl3")
        self.assertEqual(data["remotes"][3]["disabled"], True)

        client.run("remote disable *")
        registry = load(client.cache.remotes_path)
        data = json.loads(registry)
        for remote in data["remotes"]:
            self.assertEqual(remote["disabled"], True)

        client.run("remote enable *")
        registry = load(client.cache.remotes_path)
        data = json.loads(registry)
        for remote in data["remotes"]:
            self.assertNotIn("disabled", remote)

    def test_invalid_remote_disable(self):
        client = TestClient()

        client.run("remote disable invalid_remote", assert_error=True)
        self.assertIn("ERROR: Remote 'invalid_remote' not found in remotes", client.out)

        client.run("remote enable invalid_remote", assert_error=True)
        self.assertIn("ERROR: Remote 'invalid_remote' not found in remotes", client.out)

        client.run("remote disable invalid_wildcard_*")

    def test_remote_disable_already_set(self):
        """
        Check that we don't raise an error if the remote is already in the required state
        """
        client = TestClient()

        client.run("remote add my-remote0 http://someurl0")
        client.run("remote enable my-remote0")
        client.run("remote enable my-remote0")

        client.run("remote disable my-remote0")
        client.run("remote disable my-remote0")

    def test_verify_ssl_error(self):
        client = TestClient()
        client.run("remote add my-remote http://someurl some_invalid_option=foo", assert_error=True)

        self.assertIn("ERROR: Unrecognized boolean value 'some_invalid_option=foo'",
                      client.out)
        data = json.loads(load(client.cache.remotes_path))
        self.assertEqual(data["remotes"], [])

    def test_errors(self):
        self.client.run("remote update origin url", assert_error=True)
        self.assertIn("ERROR: Remote 'origin' not found in remotes", self.client.out)

        self.client.run("remote remove origin", assert_error=True)
        self.assertIn("ERROR: No remote 'origin' defined in remotes", self.client.out)

    def test_duplicated_error(self):
        """ check remote name and URL are not duplicated
        """
        self.client.run("remote add remote1 http://otherurl", assert_error=True)
        self.assertIn("ERROR: Remote 'remote1' already exists in remotes (use update to modify)",
                      self.client.out)

        self.client.run("remote list")
        url = str(self.client.out).split()[1]
        self.client.run("remote add newname %s" % url, assert_error=True)
        self.assertIn("Remote 'remote0' already exists with same URL", self.client.out)

        self.client.run("remote update remote1 %s" % url, assert_error=True)
        self.assertIn("Remote 'remote0' already exists with same URL", self.client.out)

    def test_basic_refs(self):
        self.client.run("remote add_ref Hello/0.1@user/testing remote0")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.out)

        self.client.run("remote add_ref Hello1/0.1@user/testing remote1")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.out)
        self.assertIn("Hello1/0.1@user/testing: remote1", self.client.out)

        self.client.run("remote remove_ref Hello1/0.1@user/testing")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.out)
        self.assertNotIn("Hello1/0.1@user/testing", self.client.out)

        self.client.run("remote add_ref Hello1/0.1@user/testing remote1")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.out)
        self.assertIn("Hello1/0.1@user/testing: remote1", self.client.out)

        self.client.run("remote update_ref Hello1/0.1@user/testing remote2")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.out)
        self.assertIn("Hello1/0.1@user/testing: remote2", self.client.out)

    def test_package_refs(self):

        self.client.run("remote add_pref Hello/0.1@user/testing:555 remote0")
        self.client.run("remote list_pref Hello/0.1@user/testing")
        self.assertIn("Hello/0.1@user/testing:555: remote0", self.client.out)

        self.client.run("remote add_pref Hello1/0.1@user/testing:555 remote1")
        self.client.run("remote list_pref Hello1/0.1@user/testing")
        self.assertIn("Hello1/0.1@user/testing:555: remote1", self.client.out)

        self.client.run("remote remove_pref Hello1/0.1@user/testing:555")
        self.client.run("remote list_pref Hello1/0.1@user/testing")
        self.assertNotIn("Hello1/0.1@user/testing:555", self.client.out)

        self.client.run("remote add_pref Hello1/0.1@user/testing:555 remote0")
        self.client.run("remote add_pref Hello1/0.1@user/testing:666 remote1")
        self.client.run("remote list_pref Hello1/0.1@user/testing")
        self.assertIn("Hello1/0.1@user/testing:555: remote0", self.client.out)
        self.assertIn("Hello1/0.1@user/testing:666: remote1", self.client.out)

        self.client.run("remote update_pref Hello1/0.1@user/testing:555 remote2")
        self.client.run("remote list_pref Hello1/0.1@user/testing")
        self.assertIn("Hello1/0.1@user/testing:555: remote2", self.client.out)
        self.assertIn("Hello1/0.1@user/testing:666: remote1", self.client.out)

    def test_missing_subarguments(self):
        self.client.run("remote", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", self.client.out)

    def test_invalid_url(self):
        self.client.run("remote add foobar foobar.com")
        self.assertIn("WARN: The URL 'foobar.com' is invalid. It must contain scheme and hostname.",
                      self.client.out)
        self.client.run("remote list")
        self.assertIn("foobar.com", self.client.out)

        self.client.run("remote update foobar pepe.org")
        self.assertIn("WARN: The URL 'pepe.org' is invalid. It must contain scheme and hostname.",
                      self.client.out)
        self.client.run("remote list")
        self.assertIn("pepe.org", self.client.out)

    def test_metadata_editable_packages(self):
        """
        Check that 'conan remote' commands work with editable packages
        """
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("create . pkg/1.1@lasote/stable")
        self.client.run("upload pkg/1.1@lasote/stable --all -c --remote remote1")
        self.client.run("remove -f pkg/1.1@lasote/stable")
        self.client.run("install pkg/1.1@lasote/stable")
        self.assertIn("pkg/1.1@lasote/stable: Package installed", self.client.out)
        self.client.run("remote list_ref")
        self.assertIn("pkg/1.1@lasote/stable: remote1", self.client.out)
        self.client.run("editable add . pkg/1.1@lasote/stable")
        # Check add --force, update and rename
        self.client.run("remote add remote2 %s --force" % self.servers["remote1"].fake_url)
        self.client.run("remote update remote2 %sfake" % self.servers["remote1"].fake_url)
        self.client.run("remote rename remote2 remote-fake")
        self.client.run("editable remove pkg/1.1@lasote/stable")
        # Check associated remote has changed name
        self.client.run("remote list_ref")
        self.assertIn("pkg/1.1@lasote/stable: remote-fake", self.client.out)
        # Check remove
        self.client.run("editable add . pkg/1.1@lasote/stable")
        self.client.run("remote remove remote-fake")
        self.client.run("remote list")
        self.assertIn("remote0: %s" % self.servers["remote0"].fake_url, self.client.out)
        self.assertNotIn("remote-fake", self.client.out)
        # Check clean
        self.client.run("editable remove pkg/1.1@lasote/stable")
        self.client.run("remove -f pkg/1.1@lasote/stable")
        self.client.run("remote add remote1 %s" % self.servers["remote1"].fake_url)
        self.client.run("install pkg/1.1@lasote/stable")
        self.client.run("editable add . pkg/1.1@lasote/stable")
        self.client.run("remote clean")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertNotIn("remote0", self.client.out)

    def test_remove_package_empty(self):
        self.client.save({"conanfile.py": GenConanfile("name", "version")})
        self.client.run("export . name/version@lasote/stable")
        self.client.run("upload name/version@lasote/stable --remote remote1")
        self.client.run("remove -f -p -r remote1 name/version@lasote/stable")
