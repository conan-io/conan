import unittest
from conans.test.tools import TestClient, TestServer
from collections import OrderedDict


class RemoteTest(unittest.TestCase):

    def setUp(self):
        self.servers = OrderedDict()
        self.users = {}
        for i in range(3):
            test_server = TestServer()
            self.servers["remote%d" % i] = test_server
            self.users["remote%d" % i] = [("lasote", "mypass")]

        self.client = TestClient(servers=self.servers, users=self.users)

    def basic_test(self):
        self.client.run("remote list")
        self.assertIn("remote0: http://", self.client.user_io.out)
        self.assertIn("remote1: http://", self.client.user_io.out)
        self.assertIn("remote2: http://", self.client.user_io.out)

        self.client.run("remote add origin https://myurl")
        self.client.run("remote list")
        self.assertIn("origin: https://myurl", self.client.user_io.out)

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

    def errors_test(self):
        self.client.run("remote update origin url", ignore_error=True)
        self.assertIn("ERROR: origin not found in remotes", self.client.user_io.out)

        self.client.run("remote remove origin", ignore_error=True)
        self.assertIn("ERROR: origin not found in remotes", self.client.user_io.out)

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
