from conans.errors import ConanException
from conans.util.config_parser import ConfigParser
import unittest
from conans.util.files import save
import os
from conans.server.conf import ConanServerConfigParser
from datetime import timedelta
from conans.test.utils.test_files import temp_folder
from conans.paths import conan_expand_user


fileconfig = '''
[server]
jwt_secret: mysecret
jwt_expire_minutes: 121
disk_storage_path: %s
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
        self.storage_path = os.path.join(self.file_path, "storage")
        save(server_conf, fileconfig % self.storage_path)
        self.environ = {}

    def test_unexpected_section(self):
        text = """
[one]
text=value
[two]
other=var
[three]
var
[moon]
var=walker
"""

        self.assertRaises(ConanException, ConfigParser, text, ["one", "two", "three"])
        conf = ConfigParser(text, ["one", "two", "three"], raise_unexpected_field=False)
        self.assertEquals(conf.one, "text=value")
        self.assertEquals(conf.two, "other=var")
        self.assertEquals(conf.three, "var")
        self.assertEquals(conf.moon, "var=walker")
        with self.assertRaisesRegexp(ConanException, "Unrecognized field 'NOEXIST'"):
            conf.NOEXIST

        # IF an old config file is readed but the section is in the list, just return it empty
        text = """
[one]
text=value
        """
        conf = ConfigParser(text, ["one", "two", "three"], raise_unexpected_field=False)
        self.assertEquals(conf.two, "")

    def test_values(self):
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        self.assertEquals(config.jwt_secret, "mysecret")
        self.assertEquals(config.jwt_expire_time, timedelta(minutes=121))
        self.assertEquals(config.disk_storage_path, self.storage_path)
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
        self.assertEquals(config.disk_storage_path, conan_expand_user(tmp_storage))
        self.assertFalse(config.ssl_enabled)
        self.assertEquals(config.port, 1233)
        self.assertEquals(config.write_permissions, [("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.read_permissions, [("*/*@*/*", "*"),
                                                    ("openssl/2.0.1@lasote/testing", "pepe")])
        self.assertEquals(config.users, {"lasote": "lasotepass", "pepe2": "pepepass2"})
