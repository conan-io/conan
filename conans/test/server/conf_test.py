import unittest
import os
from conans.errors import ConanException
from conans.util.files import save, load
from conans.util.log import logger
from conans.server.conf import ConanServerConfigParser
from datetime import timedelta
from conans.test.utils.test_files import temp_folder
from conans.paths import conan_expand_user
from conans.server.migrate import migrate_and_get_server_config
from conans import __version__ as VERSION

fileconfig = '''
[server]
jwt_secret: mysecret
jwt_expire_minutes: 121
disk_storage_path: %s
store_adapter: disk
ssl_enabled: true
port: 9220
public_port: 
host_name: noname

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
        self.conf_path = os.path.join(self.file_path, ".conan_server")
        server_conf = os.path.join(self.conf_path, 'server.conf')
        self.storage_path = os.path.join(self.file_path, "storage")
        save(server_conf, fileconfig % self.storage_path)
        self.environ = {}

    def writeVersion(self, version):
        # A version.txt file 
        save(os.path.join(self.conf_path, "version.txt"), version)
    
    def readVersion(self):
        return load(os.path.join(self.conf_path, "version.txt"))

    def loadConfig(self):
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        #trigger _get_file_conf
        config._get_file_conf("server", "port")
        return config
    
    def writeConfig(self, config):
        with open(config.config_filename, 'w') as fp:
            config.write(fp)


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
        self.assertEquals(config.public_port, 9220)
        self.assertEquals(config.host_name, "noname")
        self.assertEquals(config.public_url, "https://noname:9220/v1")


        # set public port
        config.set("server","public_port", "5555")
        self.assertEquals(config.public_port, 5555)
        # should throw without updown_secret
        config.set("server", "updown_secret", "")
        with self.assertRaises(ConanException):
            config.updown_secret
        # Now check with environments
        tmp_storage = temp_folder()
        self.environ["CONAN_STORAGE_PATH"] = tmp_storage
        self.environ["CONAN_JWT_SECRET"] = "newkey"
        self.environ["CONAN_JWT_EXPIRE_MINUTES"] = "123"
        self.environ["CONAN_SSL_ENABLED"] = "False"
        self.environ["CONAN_SERVER_PORT"] = "1233"
        self.environ["CONAN_SERVER_USERS"] = "lasote:lasotepass,pepe2:pepepass2"
        self.environ["CONAN_SERVER_PUBLIC_PORT"] = "1234"

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
        self.assertEquals(config.public_port, 1234)
        self.assertEquals(config.public_url, "http://noname:1234/v1")
    
    
    def test_migration_without_store_adapter(self):
        """ Seems to be here for some reason """
        config1 = self.loadConfig()
        config1.set("server", "store_adapter", "other")
        self.writeConfig(config1)
        #migrate
        self.assertEqual(config1.store_adapter, "other")
        migrate_and_get_server_config(self.file_path)
        self.assertEqual(self.readVersion(), VERSION)
        config = ConanServerConfigParser(self.file_path)
        self.assertEqual(config.store_adapter, "other")

    def test_migration_from_0_1(self):
        """ Should delete all files """
        self.writeVersion("0.1")
        migrate_and_get_server_config(self.file_path, self.storage_path)
        self.assertFalse(os.path.exists(self.storage_path))
        self.assertFalse(os.path.exists(os.path.join(self.conf_path, "server.conf")))
    
    def test_migration_from_0_19(self):
        """ Should add authentication and htpasswd_file """
        migrate_and_get_server_config(self.file_path, self.storage_path)
        # load it
        config = self.loadConfig()
        self.assertEquals(config.authentication, ["basic"])
        # assumes that the conig file has been loaded
        self.assertEquals(config.get("server", "htpasswd_file"), "")
        # now check with
        self.environ["CONAN_SERVER_AUTHENTICATION"] = "htpasswd,ldap,test"
        self.environ["CONAN_HTPASSWD_FILE"] = "fancyfile"
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        self.assertEquals(config.authentication, ["htpasswd", "ldap", "test"])
        self.assertEquals(config.htpasswd_file, "fancyfile")

    def test_auto_creates_conf(self):
        """ Should automatically create a config file """
        os.remove(os.path.join(self.conf_path, "server.conf"))
        config = ConanServerConfigParser(self.file_path, environment=self.environ)
        self.assertTrue(config.jwt_secret != None)
        self.assertTrue(os.path.exists(os.path.join(self.conf_path, "server.conf")))
    
    def test_invalid_section(self):
        """ Should throw if requesting unknown section """
        config = self.loadConfig()
        with self.assertRaises(ConanException):
            config._get_file_conf("notdefinedsection")