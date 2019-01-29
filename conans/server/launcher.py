#!/usr/bin/python
import argparse
import os

from conans import SERVER_CAPABILITIES
from conans import __version__ as SERVER_VERSION, REVISIONS
from conans.model.version import Version
from conans.paths import conan_expand_user
from conans.server.conf import MIN_CLIENT_COMPATIBLE_VERSION
from conans.server.conf import get_server_store

from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager
from conans.server.crypto.jwt.jwt_updown_manager import JWTUpDownAuthManager
from conans.server.migrate import migrate_and_get_server_config
from conans.server.plugin_loader import load_authentication_plugin
from conans.server.rest.server import ConanServer

from conans.server.service.authorize import BasicAuthorizer, BasicAuthenticator


class ServerLauncher(object):
    def __init__(self, force_migration=False):
        self.force_migration = force_migration
        user_folder = conan_expand_user("~")
        server_folder = os.path.join(user_folder, '.conan_server')

        server_config = migrate_and_get_server_config(user_folder, None, self.force_migration)
        custom_auth = server_config.custom_authenticator
        if custom_auth:
            authenticator = load_authentication_plugin(server_folder, custom_auth)
        else:
            authenticator = BasicAuthenticator(dict(server_config.users))

        authorizer = BasicAuthorizer(server_config.read_permissions,
                                     server_config.write_permissions)
        credentials_manager = JWTCredentialsManager(server_config.jwt_secret,
                                                    server_config.jwt_expire_time)

        updown_auth_manager = JWTUpDownAuthManager(server_config.updown_secret,
                                                   server_config.authorize_timeout)

        server_store = get_server_store(server_config.disk_storage_path,
                                        server_config.public_url,
                                        updown_auth_manager=updown_auth_manager)

        server_capabilities = SERVER_CAPABILITIES
        server_capabilities.append(REVISIONS)

        self.server = ConanServer(server_config.port, credentials_manager, updown_auth_manager,
                                  authorizer, authenticator, server_store,
                                  server_capabilities)
        if not self.force_migration:
            print("***********************")
            print("Using config: %s" % server_config.config_filename)
            print("Storage: %s" % server_config.disk_storage_path)
            print("Public URL: %s" % server_config.public_url)
            print("PORT: %s" % server_config.port)
            print("***********************")

    def launch(self):
        if not self.force_migration:
            self.server.run(host="0.0.0.0")
