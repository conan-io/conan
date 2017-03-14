import unittest
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
        unittest.TestCase.setUp(self)
        self.servers = {}
        self.conan_reference = ConanFileReference.loads("openssl/2.0.1@lasote/testing")
        # Create a default remote. R/W is not authorized for conan_reference, just for pepe and owner
        self.test_server = TestServer([(str(self.conan_reference), "pepe")],  # read permissions
                                      [(str(self.conan_reference), "pepe")],  # write permissions
                                      users={"lasote": "mypass",
                                             "pepe": "pepepass"})  # exported users and passwords
        self.servers["default"] = self.test_server

    def retries_test(self):
        """Bad login 2 times"""
        self.conan = TestClient(servers=self.servers, users={"default": [("baduser", "badpass"),
                                                                       ("baduser", "badpass2"),
                                                                       ("pepe", "pepepass")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export lasote")
        errors = self.conan.run("upload %s" % str(self.conan_reference))
        # Check that return was  ok
        self.assertFalse(errors)
        # Check that upload was granted
        self.assertTrue(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed two times before ok
        self.assertEquals(self.conan.user_io.login_index["default"], 3)

    def max_retries_test(self):
        """Bad login 3 times"""
        self.conan = TestClient(servers=self.servers, users={"default": [("baduser", "badpass"),
                                                                    ("baduser", "badpass2"),
                                                                    ("baduser3", "badpass3")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export lasote -p ./ ")
        errors = self.conan.run("upload %s" % str(self.conan_reference), ignore_error=True)
        # Check that return was not ok
        self.assertTrue(errors)
        # Check that upload was not granted
        self.assertFalse(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed all times
        self.assertEquals(self.conan.user_io.login_index["default"], 3)
