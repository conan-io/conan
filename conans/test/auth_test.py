import unittest
from conans.errors import ConanException
from conans.test.tools import TestServer, TestClient
from conans.test.server.utils.dummy_server_conf import create_dummy_htpasswd
from conans.paths import CONANFILE
from conans.util.files import save, mkdir
from conans.model.ref import ConanFileReference
from conans.test.utils.test_files import temp_folder
import os

conan_content = """
from conans import ConanFile

class OpenSSLConan(ConanFile):
    name = "openssl"
    version = "2.0.1"
    files = '*'
"""


class AuthorizeTest(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.servers = {}
        cls.conan_reference = ConanFileReference.loads("openssl/2.0.1@lasote/testing")
        users = {"lasote": "mypass", "pepe": "pepepass"}
        # Create a default remote. R/W is not authorized for conan_reference, just for pepe and owner
        cls.test_server = TestServer([(str(cls.conan_reference), "pepe")],  # read permissions
                                      [(str(cls.conan_reference), "pepe")],  # write permissions
                                      users=users)  # exported users and passwords
        cls.servers["default"] = cls.test_server
        #create htpasswd remote
        base_path = temp_folder()
        mkdir(os.path.join(base_path,".conan_server"))
        create_dummy_htpasswd(os.path.join(base_path,".conan_server", ".htpasswd"), users)
        cls.test_server2 = TestServer([(str(cls.conan_reference), "pepe")],  # read permissions
                                      [(str(cls.conan_reference), "pepe")],  # write permissions
                                      base_path=base_path,#custom base path here due to .htpasswd file
                                      authentication={"htpasswd": ".htpasswd"})
        cls.servers["htpasswd"] = cls.test_server2

    def retries_test(self):
        """Bad login 2 times"""
        self.conan = TestClient(servers=self.servers, users={"default": [("baduser", "badpass"),
                                                                       ("baduser", "badpass2"),
                                                                       ("pepe", "pepepass")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export lasote")
        errors = self.conan.run("upload %s --remote default" % str(self.conan_reference))
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
        errors = self.conan.run("upload %s --remote default" % str(self.conan_reference), ignore_error=True)
        # Check that return was not ok
        self.assertTrue(errors)
        # Check that upload was not granted
        self.assertFalse(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed all times
        self.assertEquals(self.conan.user_io.login_index["default"], 3)

    def retries_htpasswd_test(self):
        """Bad login 2 times using htpasswd"""
        self.conan = TestClient(servers=self.servers, users={"htpasswd": [("baduser", "badpass"),
                                                                       ("baduser", "badpass2"),
                                                                       ("pepe", "pepepass")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export lasote")
        errors = self.conan.run("upload %s --remote htpasswd" % str(self.conan_reference))
        # Check that return was  ok
        self.assertFalse(errors)
        # Check that upload was granted
        self.assertTrue(os.path.exists(self.test_server2.paths.export(self.conan_reference)))

        # Check that login failed two times before ok
        self.assertEquals(self.conan.user_io.login_index["htpasswd"], 3)

    def max_retries_htpasswd_test(self):
        """Bad login 3 times using htpasswd"""
        self.conan = TestClient(servers=self.servers, users={"htpasswd": [("baduser", "badpass"),
                                                                    ("baduser", "badpass2"),
                                                                    ("baduser3", "badpass3")]})
        save(os.path.join(self.conan.current_folder, CONANFILE), conan_content)
        self.conan.run("export lasote -p ./ ")
        errors = self.conan.run("upload %s --remote htpasswd" % str(self.conan_reference), ignore_error=True)
        # Check that return was not ok
        self.assertTrue(errors)
        # Check that upload was not granted
        self.assertFalse(os.path.exists(self.test_server.paths.export(self.conan_reference)))

        # Check that login failed all times
        self.assertEquals(self.conan.user_io.login_index["htpasswd"], 3)

    def invalid_authorizer_test(self):
        with self.assertRaises(ConanException):
            TestServer(authentication="unknown")
