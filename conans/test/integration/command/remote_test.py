import json
import unittest
from collections import OrderedDict

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import load


class RemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server

        self.client = TestClient(servers=self.servers, inputs=3*["admin", "password"])

    def test_list_json(self):
        self.client.run("remote list --format=json")
        data = json.loads(self.client.stdout)

        assert data[0]["name"] == "remote0"
        assert data[1]["name"] == "remote1"
        assert data[2]["name"] == "remote2"
        # TODO: Check better

    def test_basic(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.out)
        self.assertIn("remote1: http://", self.client.out)
        self.assertIn("remote2: http://", self.client.out)

        self.client.run("remote add origin https://myurl")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        self.assertIn("origin: https://myurl", lines[3])

        self.client.run("remote update origin --url https://2myurl")
        self.client.run("remote list")
        self.assertIn("origin: https://2myurl", self.client.out)

        self.client.run("remote update remote0 --url https://remote0url")
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
        self.client.run("remote remove remote1")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertIn("remote0", self.client.out)
        self.assertIn("remote2", self.client.out)
        self.client.run("remote remove remote2")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertIn("remote0", self.client.out)
        self.assertNotIn("remote2", self.client.out)

    def test_remove_remote_all(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.out)
        self.assertIn("remote1: http://", self.client.out)
        self.assertIn("remote2: http://", self.client.out)
        self.client.run("remote remove *")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertNotIn("remote0", self.client.out)
        self.assertNotIn("remote2", self.client.out)

    def test_remove_remote_no_user(self):
        self.client.save({"conanfile.py": GenConanfile()})
        self.client.run("remote remove remote0")
        self.client.run("remote list")
        self.assertNotIn("remote0", self.client.out)

    def test_rename(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export . --name=hello --version=0.1 --user=user --channel=testing")
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote rename r2 mynewr2")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("mynewr2: https://r2", lines[1])
        self.assertIn("r3: https://r3", lines[2])

        # Rename to an existing one
        client.run("remote rename mynewr2 r1", assert_error=True)
        self.assertIn("Remote 'r1' already exists", client.out)

    def test_insert(self):
        self.client.run("remote add origin https://myurl --index", assert_error=True)

        self.client.run("remote add origin https://myurl --index=0")
        self.client.run("remote add origin2 https://myurl2 --index=0")
        self.client.run("remote list")
        lines = str(self.client.out).splitlines()
        self.assertIn("origin2: https://myurl2", lines[0])
        self.assertIn("origin: https://myurl", lines[1])

        self.client.run("remote add origin3 https://myurl3 --index=1")
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

        client.run("remote update r2 --url https://r2new --index=0")
        client.run("remote list")
        lines = str(client.out).splitlines()
        self.assertIn("r2: https://r2new", lines[0])
        self.assertIn("r1: https://r1", lines[1])
        self.assertIn("r3: https://r3", lines[2])

        client.run("remote update r2 --url https://r2new2")
        client.run("remote update r2 --index=2")
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
        client.run("remote update r2 --url https://r2")
        client.run("remote update r2 --index 0")
        client.run("remote list")
        self.assertLess(str(client.out).find("r2"), str(client.out).find("r1"))
        self.assertLess(str(client.out).find("r1"), str(client.out).find("r3"))

    def test_verify_ssl(self):
        client = TestClient()
        client.run("remote add my-remote http://someurl")
        client.run("remote add my-remote2 http://someurl2 --insecure")
        client.run("remote add my-remote3 http://someurl3")

        registry = load(client.cache.remotes_path)
        data = json.loads(registry)
        self.assertEqual(data["remotes"][0]["name"], "my-remote")
        self.assertEqual(data["remotes"][0]["url"], "http://someurl")
        self.assertEqual(data["remotes"][0]["verify_ssl"], True)

        self.assertEqual(data["remotes"][1]["name"], "my-remote2")
        self.assertEqual(data["remotes"][1]["url"], "http://someurl2")
        self.assertEqual(data["remotes"][1]["verify_ssl"], False)

        self.assertEqual(data["remotes"][2]["name"], "my-remote3")
        self.assertEqual(data["remotes"][2]["url"], "http://someurl3")
        self.assertEqual(data["remotes"][2]["verify_ssl"], True)

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

        # check that they are still listed, as disabled
        client.run("remote list *")
        assert "my-remote0: http://someurl0 [Verify SSL: True, Enabled: False]" in client.out
        assert "my-remote3: http://someurl3 [Verify SSL: True, Enabled: False]" in client.out

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
        msg = "ERROR: Remote 'invalid_remote' can't be found or is disabled"
        self.assertIn(msg, client.out)

        client.run("remote enable invalid_remote", assert_error=True)
        self.assertIn(msg, client.out)

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

        self.assertIn("unrecognized arguments: some_invalid_option=foo", client.out)
        data = json.loads(load(client.cache.remotes_path))
        self.assertEqual(data["remotes"], [])

    def test_errors(self):
        self.client.run("remote update origin --url http://foo.com", assert_error=True)
        self.assertIn("ERROR: Remote 'origin' not found in remotes", self.client.out)

        self.client.run("remote remove origin", assert_error=True)
        self.assertIn("ERROR: Remote 'origin' can't be found or is disabled", self.client.out)

    def test_duplicated_error(self):
        """ check remote name and URL are not duplicated
        """
        self.client.run("remote add remote1 http://otherurl", assert_error=True)
        self.assertIn("ERROR: Remote 'remote1' already exists in remotes (use update to modify)",
                      self.client.out)

        self.client.run("remote list")
        url = str(self.client.out).split()[1]
        self.client.run("remote add newname %s" % url)
        # If you write the same URL, up to you
        self.client.run("remote update remote1 --url %s" % url)

        remote1 = self.client.api.remotes.get("remote1")
        assert remote1.url == url

    def test_missing_subarguments(self):
        self.client.run("remote", assert_error=True)
        self.assertIn("ERROR: Exiting with code: 2", self.client.out)

    def test_invalid_url(self):
        self.client.run("remote add foobar foobar.com")
        self.assertIn("WARN: The URL 'foobar.com' is invalid. It must contain scheme and hostname.",
                      self.client.out)
        self.client.run("remote list")
        self.assertIn("foobar.com", self.client.out)

        self.client.run("remote update foobar --url pepe.org")
        self.assertIn("WARN: The URL 'pepe.org' is invalid. It must contain scheme and hostname.",
                      self.client.out)
        self.client.run("remote list")
        self.assertIn("pepe.org", self.client.out)
