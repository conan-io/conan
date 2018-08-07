import unittest
from conans.test.utils.tools import TestClient, TestServer
from collections import OrderedDict
from conans.util.files import load
import re


class RemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.client = TestClient(servers=self.servers, users=self.users)

    def list_raw_test(self):
        self.client.run("remote list --raw")
        output = re.sub("http:\/\/fake.+\.com", "http://fake.com", str(self.client.out))
        self.assertIn("remote0 http://fake.com True", output)
        self.assertIn("remote1 http://fake.com True", output)
        self.assertIn("remote2 http://fake.com True", output)

    def basic_test(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.user_io.out)
        self.assertIn("remote1: http://", self.client.user_io.out)
        self.assertIn("remote2: http://", self.client.user_io.out)

        self.client.run("remote add origin https://myurl")
        self.client.run("remote list")
        lines = str(self.client.user_io.out).splitlines()
        self.assertIn("origin: https://myurl", lines[3])

        self.client.run("remote update origin https://2myurl")
        self.client.run("remote list")
        self.assertIn("origin: https://2myurl", self.client.user_io.out)

        self.client.run("remote update remote0 https://remote0url")
        self.client.run("remote list")
        output = str(self.client.user_io.out)
        self.assertIn("remote0: https://remote0url", output.splitlines()[0])

        self.client.run("remote remove remote0")
        self.client.run("remote list")
        output = str(self.client.user_io.out)
        self.assertIn("remote1: http://", output.splitlines()[0])

    def remove_remote_test(self):
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
        registry = load(self.client.client_cache.registry)
        self.assertNotIn("Hello2/0.1@user/testing", registry)
        self.assertIn("Hello/0.1@user/testing", registry)

        self.client.run("remote remove remote2")
        self.client.run("remote list")
        self.assertNotIn("remote1", self.client.out)
        self.assertIn("remote0", self.client.out)
        self.assertNotIn("remote2", self.client.out)
        self.client.run("remote list_ref")
        self.assertNotIn("Hello2/0.1@user/testing", self.client.out)
        self.assertNotIn("Hello/0.1@user/testing", self.client.out)
        registry = load(self.client.client_cache.registry)
        self.assertNotIn("Hello2/0.1@user/testing", registry)
        self.assertNotIn("Hello/0.1@user/testing", registry)

    def add_force_test(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote add_ref Hello/0.1@user/testing r2")
        client.run("remote add_ref Hello2/0.1@user/testing r1")

        client.run("remote add r4 https://r4 -f")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r2: https://r2", lines[1])
        self.assertIn("r3: https://r3", lines[2])
        self.assertIn("r4: https://r4", lines[3])

        client.run("remote add r2 https://newr2 -f")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r4: https://r4", lines[2])
        self.assertIn("r2: https://newr2", lines[3])

        client.run("remote add newr1 https://r1 -f")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r3: https://r3", lines[0])
        self.assertIn("r4: https://r4", lines[1])
        self.assertIn("r2: https://newr2", lines[2])
        self.assertIn("newr1: https://r1", lines[3])
        client.run("remote list_ref")
        self.assertIn("Hello2/0.1@user/testing: newr1", client.out)
        self.assertIn("Hello/0.1@user/testing: r2", client.out)

        client.run("remote add newr1 https://newr1 -f -i")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("newr1: https://newr1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r4: https://r4", lines[2])
        self.assertIn("r2: https://newr2", lines[3])

    def rename_test(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")
        client.run("remote add_ref Hello/0.1@user/testing r2")
        client.run("remote rename r2 mynewr2")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("mynewr2: https://r2", lines[1])
        self.assertIn("r3: https://r3", lines[2])
        client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: mynewr2", client.out)

    def insert_test(self):
        self.client.run("remote add origin https://myurl --insert")
        self.client.run("remote list")
        first_line = str(self.client.user_io.out).splitlines()[0]
        self.assertIn("origin: https://myurl", first_line)

        self.client.run("remote add origin2 https://myurl2 --insert=0")
        self.client.run("remote list")
        lines = str(self.client.user_io.out).splitlines()
        self.assertIn("origin2: https://myurl2", lines[0])
        self.assertIn("origin: https://myurl", lines[1])

        self.client.run("remote add origin3 https://myurl3 --insert=1")
        self.client.run("remote list")
        lines = str(self.client.user_io.out).splitlines()
        self.assertIn("origin2: https://myurl2", lines[0])
        self.assertIn("origin3: https://myurl3", lines[1])
        self.assertIn("origin: https://myurl", lines[2])

    def update_test_insert(self):
        client = TestClient()
        client.run("remote add r1 https://r1")
        client.run("remote add r2 https://r2")
        client.run("remote add r3 https://r3")

        client.run("remote update r2 https://r2new --insert")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r2: https://r2new", lines[0])
        self.assertIn("r1: https://r1", lines[1])
        self.assertIn("r3: https://r3", lines[2])

        client.run("remote update r2 https://r2new2 --insert 2")
        client.run("remote list")
        lines = str(client.user_io.out).splitlines()
        self.assertIn("r1: https://r1", lines[0])
        self.assertIn("r3: https://r3", lines[1])
        self.assertIn("r2: https://r2new2", lines[2])

    def verify_ssl_test(self):
        client = TestClient()
        client.run("remote add my-remote http://someurl TRUE")
        client.run("remote add my-remote2 http://someurl2 yes")
        client.run("remote add my-remote3 http://someurl3 FALse")
        client.run("remote add my-remote4 http://someurl4 No")
        registry = load(client.client_cache.registry)
        self.assertIn("my-remote http://someurl True", registry)
        self.assertIn("my-remote2 http://someurl2 True", registry)
        self.assertIn("my-remote3 http://someurl3 False", registry)
        self.assertIn("my-remote4 http://someurl4 False", registry)

    def verify_ssl_error_test(self):
        client = TestClient()
        error = client.run("remote add my-remote http://someurl some_invalid_option=foo",
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Unrecognized boolean value 'some_invalid_option=foo'",
                      client.user_io.out)
        self.assertEqual("", load(client.client_cache.registry))

    def errors_test(self):
        self.client.run("remote update origin url", ignore_error=True)
        self.assertIn("ERROR: Remote 'origin' not found in remotes", self.client.user_io.out)

        self.client.run("remote remove origin", ignore_error=True)
        self.assertIn("ERROR: Remote 'origin' not found in remotes", self.client.user_io.out)

    def duplicated_error_tests(self):
        """ check remote name and URL are not duplicated
        """
        error = self.client.run("remote add remote1 http://otherurl", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Remote 'remote1' already exists in remotes (use update to modify)",
                      self.client.user_io.out)

        self.client.run("remote list")
        url = str(self.client.user_io.out).split()[1]
        error = self.client.run("remote add newname %s" % url, ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Remote 'remote0' already exists with same URL",
                      self.client.user_io.out)

        error = self.client.run("remote update remote1 %s" % url, ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Remote 'remote0' already exists with same URL",
                      self.client.user_io.out)

    def basic_refs_test(self):
        self.client.run("remote add_ref Hello/0.1@user/testing remote0")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.user_io.out)

        self.client.run("remote add_ref Hello1/0.1@user/testing remote1")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.user_io.out)
        self.assertIn("Hello1/0.1@user/testing: remote1", self.client.user_io.out)

        self.client.run("remote remove_ref Hello1/0.1@user/testing")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.user_io.out)
        self.assertNotIn("Hello1/0.1@user/testing", self.client.user_io.out)

        self.client.run("remote add_ref Hello1/0.1@user/testing remote1")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.user_io.out)
        self.assertIn("Hello1/0.1@user/testing: remote1", self.client.user_io.out)

        self.client.run("remote update_ref Hello1/0.1@user/testing remote2")
        self.client.run("remote list_ref")
        self.assertIn("Hello/0.1@user/testing: remote0", self.client.user_io.out)
        self.assertIn("Hello1/0.1@user/testing: remote2", self.client.user_io.out)
