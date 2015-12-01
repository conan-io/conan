import unittest
from conans.util.files import save
import os
from conans.server.conf import ConanServerConfigParser
from datetime import timedelta
from conans.test.utils.test_files import temp_folder


fileconfig = '''
[server]
jwt_secret: mysecret
jwt_expire_minutes: 121
disk_storage_path: ~/.conans
ssl_enabled: true
port: 9220


[write_permissions]
openssl/2.0.1@lasote/testing: pepe

[read_permissions]
*/*@*/*: *
openssl/2.0.1@lasote/testing: pepe

[users]
lasote: defaultpass
pepe: pepepass
'''


class ServerConfTest(unittest.TestCase):

    def setUp(self):
        self.file_path = temp_folder()
        server_conf = os.path.join(self.file_path, '.conan_server/server.conf')
        save(server_conf, fileconfig)
        self.environ = {}

    def test_values(self):
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        self.assertEquals(config.jwt_secret, "mysecret")
        self.assertEquals(config.jwt_expire_time, timedelta(minutes=121))
        self.assertEquals(config.disk_storage_path, os.path.normpath(os.path.expanduser("~/.conans")))
        self.assertTrue(config.ssl_enabled)
        self.assertEquals(config.port, 9220)
        self.assertEquals(config.write_permissions, [("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.read_permissions, [("*/*@*/*", "*"),
                                                    ("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.users, {"lasote": "defaultpass", "pepe": "pepepass"})

        # Now check with environments
        tmp_storage = temp_folder()
        self.environ["CONAN_STORAGE_PATH"] = tmp_storage
        self.environ["CONAN_JWT_SECRET"] = "newkey"
        self.environ["CONAN_JWT_EXPIRE_MINUTES"] = "123"
        self.environ["CONAN_SSL_ENABLED"] = "False"
        self.environ["CONAN_SERVER_PORT"] = "1233"
        self.environ["CONAN_SERVER_USERS"] = "lasote:lasotepass,pepe2:pepepass2"

        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        self.assertEquals(config.jwt_secret,  "newkey")
        self.assertEquals(config.jwt_expire_time, timedelta(minutes=123))
        self.assertEquals(config.disk_storage_path, os.path.expanduser(tmp_storage))
        self.assertFalse(config.ssl_enabled)
        self.assertEquals(config.port, 1233)
        self.assertEquals(config.write_permissions, [("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.read_permissions, [("*/*@*/*", "*"),
                                                    ("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.users, {"lasote": "lasotepass", "pepe2": "pepepass2"})
