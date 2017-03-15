import unittest
from conans.test.utils.tools import TestServer, TestClient
from conans.paths import CONANFILE
from conans.test.utils.cpp_test_files import cpp_hello_conan_files
from collections import OrderedDict
from time import sleep


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
            client.run("export lasote/stable")

    def conan_test_test(self):
        '''Checks --build in test command'''
        client_a = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                           "local": [("lasote", "mypass")]})
        client_b = TestClient(servers=self.servers, users={"default": [("lasote", "mypass")],
                                                           "local": [("lasote", "mypass")]})

        # Upload Hello0 to local and default from client_a
        self._create(client_a, "Hello0", "0.0")
        client_a.run("upload Hello0/0.0@lasote/stable -r local")
        client_a.run("upload Hello0/0.0@lasote/stable -r default")
        client_a.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: local", str(client_a.user_io.out))
        sleep(1)  # For timestamp and updates checks

        # Download Hello0 from local with client_b
        client_b.run("install Hello0/0.0@lasote/stable -r local --build missing")
        client_b.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: local", str(client_b.user_io.out))

        # Update Hello0 with client_a and reupload
        self._create(client_a, "Hello0", "0.0", modifier="\n")
        client_a.run("upload Hello0/0.0@lasote/stable -r local")

        # Execute info method in client_b, should advise that there is an update
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Updates: There is a newer version (local)", str(client_b.user_io.out))

        # Now try to update the package with install -u
        client_b.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: local", str(client_b.user_io.out))
        client_b.run("install Hello0/0.0@lasote/stable -u --build")
        self.assertIn("Hello0/0.0@lasote/stable: Retrieving from remote 'local'",
                      str(client_b.user_io.out))
        client_b.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: local", str(client_b.user_io.out))

        # Upload a new version from client A, but only to the default server (not the ref-listed)
        # Upload Hello0 to local and default from client_a
        sleep(1)  # For timestamp and updates checks
        self._create(client_a, "Hello0", "0.0", modifier="\n\n")
        client_a.run("upload Hello0/0.0@lasote/stable -r default")

        # Now client_b checks for updates without -r parameter
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Remote: local", str(client_b.user_io.out))
        self.assertIn("You have the latest version (local)", str(client_b.user_io.out))

        # But if we connect to default, should tell us that there is an update IN DEFAULT!
        client_b.run("info Hello0/0.0@lasote/stable -r default -u")
        self.assertIn("Remote: local", str(client_b.user_io.out))
        self.assertIn("There is a newer version (default)", str(client_b.user_io.out))
        client_b.run("remote list_ref")
        self.assertIn("Hello0/0.0@lasote/stable: local", str(client_b.user_io.out))

        # Well, now try to update the package with -r default -u
        client_b.run("install Hello0/0.0@lasote/stable -r default -u --build")
        self.assertIn("Hello0/0.0@lasote/stable: Retrieving from remote 'default'",
                      str(client_b.user_io.out))
        client_b.run("info Hello0/0.0@lasote/stable -u")
        self.assertIn("Updates: The local file is newer than remote's one (local)",
                      str(client_b.user_io.out))
