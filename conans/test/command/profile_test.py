import unittest

from conans.test.utils.tools import TestClient
from conans.test.utils.profiles import create_profile


class ProfileTest(unittest.TestCase):

    def empty_test(self):
        client = TestClient()
        client.run("profile list")
        self.assertIn("No profiles defined", client.user_io.out)

    def list_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile3")
        create_profile(client.client_cache.profiles_path, "profile1")
        create_profile(client.client_cache.profiles_path, "profile2")
        client.run("profile list")
        self.assertEqual(list(["profile1", "profile2", "profile3"]),
                         list(str(client.user_io.out).splitlines()))

    def show_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile1", settings={"os": "Windows"})
        create_profile(client.client_cache.profiles_path, "profile2", scopes={"test": True})
        create_profile(client.client_cache.profiles_path, "profile3",
                       env=[("package:VAR", "value"), ("CXX", "/path/tomy/g++_build"), ("CC", "/path/tomy/gcc_build")])
        client.run("profile show profile1")
        self.assertIn("    os: Windows", client.user_io.out)
        client.run("profile show profile2")
        self.assertIn("    test=True", client.user_io.out)
        client.run("profile show profile3")
        self.assertIn("    CC=/path/tomy/gcc_build", client.user_io.out)
        self.assertIn("    CXX=/path/tomy/g++_build", client.user_io.out)
        self.assertIn("    package:VAR=value", client.user_io.out)
