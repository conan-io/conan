import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.model.version import Version
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from collections import OrderedDict


class VersionCheckTest(unittest.TestCase):

    def check_versions_test(self):
        # Client deprecated
        self.servers = {"default": self._get_server(10, 5)}
        self.client = TestClient(servers=self.servers,
                                 users={"default": [("lasote", "mypass")]}, client_version=4)

        errors = self.client.run("search something -r default", ignore_error=True)
        self.assertIn("Your conan's client version is deprecated for the current remote (v10). "
                      "Upgrade conan client.", self.client.user_io.out)
        self.assertTrue(errors)  # Not Errors

        # Client outdated
        self.servers = {"default": self._get_server(10, 4)}
        self.client = TestClient(servers=self.servers,
                                 users={"default": [("lasote", "mypass")]}, client_version=4)

        errors = self.client.run("search something -r default", ignore_error=False)
        self.assertIn(" A new conan version (v10) is available in current remote. Please, "
                      "upgrade conan client to avoid deprecation.", self.client.user_io.out)
        self.assertFalse(errors)  # Not Errors

        # Client ok
        self.servers = {"default": self._get_server(10, 4)}
        self.client = TestClient(servers=self.servers,
                                 users={"default": [("lasote", "mypass")]}, client_version=10)

        errors = self.client.run("search something -r default", ignore_error=False)
        self.assertNotIn("conan client", self.client.user_io.out)
        self.assertFalse(errors)  # Not Errors

        # Server outdated
        self.servers = {"default": self._get_server(1, 1)}
        self.client = TestClient(servers=self.servers,
                                 users={"default": [("lasote", "mypass")]}, client_version=10,
                                 min_server_compatible_version=1)

        errors = self.client.run("search something -r default", ignore_error=True)
        self.assertNotIn("The conan remote version is outdated (v1). Please, contact"
                         " with your system administrator and upgrade the remote to"
                         " avoid deprecation", self.client.user_io.out)
        self.assertFalse(errors)  # No Errors

        # Server deprecated
        self.servers = {"default": self._get_server(1, 1)}
        self.client = TestClient(servers=self.servers,
                                 users={"default": [("lasote", "mypass")]}, client_version=10,
                                 min_server_compatible_version=2)

        errors = self.client.run("search something -r default", ignore_error=True)
        self.assertIn("Your conan's client is incompatible with this remote."
                      " The server is deprecated. "
                      "(v1). Please, contact with your system administrator and"
                      " upgrade the server.",
                      self.client.user_io.out)
        self.assertTrue(errors)  # Errors

    def check_multi_server_test(self):
        # Check what happen if we have 2 servers and one is outdated
        # The expected behavior: If we specify the remote with (-r), the commmand will fail
        # if the client fot that remote is outdated. If we are looking for a package (not with -r)
        # the client will look for the package on each remote.

        # Client deprecated for "the_last_server" but OK for "normal_server"
        self.servers = OrderedDict([("the_last_server", self._get_server(10, 4)),
                                    ("normal_server", self._get_server(4, 2))])

        # First upload a package ok with an ok client
        tmp_client = TestClient(servers=self.servers,
                                users={"normal_server": [("lasote", "mypass")],
                                       "the_last_server": [("lasote", "mypass")]},
                                client_version=4)
        files = cpp_hello_conan_files("Hello0", "0.1", build=False)

        tmp_client.save(files)
        tmp_client.run("export lasote/stable")
        errors = tmp_client.run("upload Hello0/0.1@lasote/stable -r normal_server --all")
        errors |= tmp_client.run("upload Hello0/0.1@lasote/stable -r the_last_server --all")
        self.assertFalse(errors)
        tmp_client.run("remote remove_ref Hello0/0.1@lasote/stable")
        # Now with a conflictive client...try to look in servers
        self.client = TestClient(servers=self.servers,
                                 users={"normal_server": [("lasote", "mypass")],
                                        "the_last_server": [("lasote", "mypass")]},
                                 client_version=2)
        errors = self.client.run("search something -r the_last_server", ignore_error=True)
        self.assertIn("Your conan's client version is deprecated for the current remote (v10). "
                      "Upgrade conan client.", self.client.user_io.out)
        self.assertTrue(errors)  # Errors

        errors = self.client.run("install Hello0/0.1@lasote/stable --build missing",
                                 ignore_error=True)
        self.assertIn("Your conan's client version is deprecated for the current remote (v10). "
                      "Upgrade conan client.", self.client.user_io.out)
        self.assertFalse(errors)  # No Errors! because it finds the package in the second remote

    def _get_server(self, server_version, min_client_compatible_version):
        server_version = str(server_version)
        min_client_compatible_version = str(min_client_compatible_version)
        return TestServer(
                          [],  # write permissions
                          users={"lasote": "mypass"},
                          server_version=Version(server_version),
                          min_client_compatible_version=Version(min_client_compatible_version))
