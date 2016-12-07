import unittest
from conans.test.tools import TestClient
from conans.test.utils.profiles import create_profile


class ProfileTest(unittest.TestCase):

    def empty_test(self):
        client = TestClient()
        client.run("profile list")
        self.assertEqual("", client.user_io.out)

    def list_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile1")
        create_profile(client.client_cache.profiles_path, "profile2")
        create_profile(client.client_cache.profiles_path, "profile3")
        client.run("profile list")
        self.assertEqual(["profile1", "profile2", "profile3"],
                         str(client.user_io.out).splitlines())

    def show_test(self):
        client = TestClient()
        create_profile(client.client_cache.profiles_path, "profile1", settings={"os": "Windows"})
        create_profile(client.client_cache.profiles_path, "profile2", scopes={"test": True})
        create_profile(client.client_cache.profiles_path, "profile3",
                       env=[("CXX", "/path/tomy/g++_build"), ("CC", "/path/tomy/gcc_build")])
        client.run("profile show profile1")
        print client.user_io.out





    """create_profile(self.client.client_cache.profiles_path, "scopes_env", settings={},
                       scopes={},  # undefined scope do not apply to my packages
                       env=[("CXX", "/path/tomy/g++_build"), ("CC", "/path/tomy/gcc_build")])"""
