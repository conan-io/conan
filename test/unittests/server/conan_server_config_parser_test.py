# -*- coding: utf-8 -*-
import os
import unittest

from conans.errors import ConanException
from conans.server.conf import ConanServerConfigParser
from conan.test.utils.test_files import temp_folder
from conans.util.files import mkdir, save


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
        with self.assertRaisesRegex(ConanException, "Password contains invalid characters. Only ASCII encoding is supported"):
            server_config.users

        save(conf_path, server_conf % "manol ito!@")
        server_config = ConanServerConfigParser(tmp_dir)
        self.assertEqual(server_config.users, {"demo": "manol ito!@"})

        # Now test from ENV
        server_config = ConanServerConfigParser(tmp_dir, environment={"CONAN_SERVER_USERS": "demo: cönan"})
        with self.assertRaisesRegex(ConanException, "Password contains invalid characters. Only ASCII encoding is supported"):
            server_config.users

        server_config = ConanServerConfigParser(tmp_dir, environment={"CONAN_SERVER_USERS": "demo:manolito!@"})
        self.assertEqual(server_config.users, {"demo": "manolito!@"})

    def test_relative_public_url(self):
        tmp_dir = temp_folder()
        server_conf = """
[server]

[write_permissions]

[users]
        """
        server_dir = os.path.join(tmp_dir, ".conan_server")
        mkdir(server_dir)
        conf_path = os.path.join(server_dir, "server.conf")
        save(conf_path, server_conf)

        server_config = ConanServerConfigParser(tmp_dir)
        self.assertEqual(server_config.public_url, "v2")

    def test_custom_server_folder_path(self):
        tmp_dir = temp_folder()
        server_dir = os.path.join(tmp_dir, ".custom_conan_server")
        mkdir(server_dir)
        conf_path = os.path.join(server_dir, "server.conf")
        server_conf = """
[server]

[write_permissions]

[users]
        """
        save(conf_path, server_conf)
        server_config = ConanServerConfigParser(server_dir, is_custom_path=True)
        self.assertEqual(server_config.conan_folder, server_dir)

    def test_custom_server_path_has_custom_data_path(self):
        tmp_dir = temp_folder()
        server_dir = os.path.join(tmp_dir, ".custom_conan_server")
        mkdir(server_dir)
        conf_path = os.path.join(server_dir, "server.conf")
        server_conf = """
[server]
disk_storage_path: ./custom_data

[write_permissions]

[users]
        """
        save(conf_path, server_conf)
        server_config = ConanServerConfigParser(server_dir, is_custom_path=True)
        self.assertEqual(server_config.disk_storage_path, os.path.join(server_dir, "custom_data"))
