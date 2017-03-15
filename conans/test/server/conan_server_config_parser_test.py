# -*- coding: utf-8 -*-
import unittest
import os

from conans.test.utils.test_files import temp_folder
from conans.util.files import save, mkdir
from conans.server.conf import ConanServerConfigParser
from conans.errors import ConanException


class ServerConfigParseTest(unittest.TestCase):

    def test_not_allowed_encoding_password(self):
        tmp_dir = temp_folder()
        server_conf = """
[server]
jwt_secret: 534534534
jwt_expire_minutes: 120
ssl_enabled: False
port: 9300
public_port:
host_name: localhost
store_adapter: disk
authorize_timeout: 1800
disk_storage_path: ~/.conan_server/data
disk_authorize_timeout: 1800
updown_secret: tbsiGzeEygYSCcNrSYcuzmZr


[write_permissions]

[users]
demo: %s
        """
        server_dir = os.path.join(tmp_dir, ".conan_server")
        mkdir(server_dir)
        conf_path = os.path.join(server_dir, "server.conf")

        save(conf_path, server_conf % "cönan")

        server_config = ConanServerConfigParser(tmp_dir)
        with self.assertRaisesRegexp(ConanException, "Password contains invalid characters. Only ASCII encoding is supported"):
            server_config.users

        save(conf_path, server_conf % "manol ito!@")
        server_config = ConanServerConfigParser(tmp_dir)
        self.assertEquals(server_config.users, {"demo": "manol ito!@"})

        # Now test from ENV
        server_config = ConanServerConfigParser(tmp_dir, environment={"CONAN_SERVER_USERS": "demo: cönan"})
        with self.assertRaisesRegexp(ConanException, "Password contains invalid characters. Only ASCII encoding is supported"):
            server_config.users

        server_config = ConanServerConfigParser(tmp_dir, environment={"CONAN_SERVER_USERS": "demo:manolito!@"})
        self.assertEquals(server_config.users, {"demo": "manolito!@"})
