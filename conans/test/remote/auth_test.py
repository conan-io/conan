import unittest

from conans import tools
from conans.test.utils.tools import TestServer, TestClient
from conans.paths import CONANFILE
from conans.util.files import save
from conans.model.ref import ConanFileReference
import os

conan_content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    files = '*'
"""


class AuthorizeTest(unittest.TestCase):

    def setUp(self):
        self.servers = {}
        self.conan_reference = ConanFileReference.loads("openssl/2.0.1@lasote/testing")
        # Create a default remote. R/W is not authorized for conan_reference,
        # just for pepe, nacho and owner
        self.test_server = TestServer([(str(self.conan_reference), "pepe,nacho@gmail.com")],  # read permissions
                                      [(str(self.conan_reference), "pepe,nacho@gmail.com")],  # write permissions
                                      users={"lasote": "mypass",
                                             "pepe": "pepepass",
                                             "nacho@gmail.com" : "nachopass",})  # exported users and passwords
        self.servers["default"] = self.test_server

    def retries_test(self):
        """Bad login 2 times"""
        self.conan = TestClient(servers=self.servers, users={"default": [("baduser", "badpass"),
                                                                         ("baduser", "badpass2"),
                                                                         ("pepe", "pepepass")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export . lasote/testing")
        errors = self.conan.run("upload %s" % str(self.conan_reference))
        # Check that return was  ok
        self.assertFalse(errors)
        # Check that upload was granted
        self.assertTrue(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed two times before ok
        self.assertEquals(self.conan.user_io.login_index["default"], 3)

    def auth_with_env_test(self):

        def _upload_with_credentials(credentials):
            cli = TestClient(servers=self.servers, users={})
            save(os.path.join(cli.current_folder, CONANFILE), conan_content)
            cli.run("export . lasote/testing")
            with tools.environment_append(credentials):
                cli.run("upload %s" % str(self.conan_reference))
            return cli

        # Try with remote name in credentials
        client = _upload_with_credentials({"CONAN_PASSWORD_DEFAULT": "pepepass",
                                           "CONAN_LOGIN_USERNAME_DEFAULT": "pepe"})
        self.assertIn("Got username 'pepe' from environment", client.user_io.out)
        self.assertIn("Got password '******' from environment", client.user_io.out)

        # Try with generic password and login
        client = _upload_with_credentials({"CONAN_PASSWORD": "pepepass",
                                           "CONAN_LOGIN_USERNAME_DEFAULT": "pepe"})
        self.assertIn("Got username 'pepe' from environment", client.user_io.out)
        self.assertIn("Got password '******' from environment", client.user_io.out)

        # Try with generic password and generic login
        client = _upload_with_credentials({"CONAN_PASSWORD": "pepepass",
                                           "CONAN_LOGIN_USERNAME": "pepe"})
        self.assertIn("Got username 'pepe' from environment", client.user_io.out)
        self.assertIn("Got password '******' from environment", client.user_io.out)

        # Bad pass raise
        with self.assertRaises(Exception):
            client = _upload_with_credentials({"CONAN_PASSWORD": "bad",
                                               "CONAN_LOGIN_USERNAME": "pepe"})
            self.assertIn("Too many failed login attempts, bye!", client.user_io.out)

    def max_retries_test(self):
        """Bad login 3 times"""
        self.conan = TestClient(servers=self.servers, users={"default": [("baduser", "badpass"),
                                                                         ("baduser", "badpass2"),
                                                                         ("baduser3", "badpass3")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export . lasote/testing")
        errors = self.conan.run("upload %s" % str(self.conan_reference), ignore_error=True)
        # Check that return was not ok
        self.assertTrue(errors)
        # Check that upload was not granted
        self.assertFalse(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed all times
        self.assertEquals(self.conan.user_io.login_index["default"], 3)

    def no_client_username_checks_test(self):
        """Checks whether client username checks are disabled."""

        # Try with a load of names that contain special characters
        self.conan = TestClient(servers=self.servers, users={"default": [
                                        ("some_random.special!characters", "badpass"),
                                        ("nacho@gmail.com", "nachopass"),
                                        ]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export . lasote/testing")
        errors = self.conan.run("upload %s" % str(self.conan_reference), ignore_error=True)

        # Check that return was ok
        self.assertFalse(errors)
        # Check that upload was granted
        self.assertTrue(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed once before ok
        self.assertEquals(self.conan.user_io.login_index["default"], 2)
