#!/usr/bin/python
from conans.server.service.authorize import BasicAuthorizer, BasicAuthenticator
from conans.server.conf import get_file_manager
from conans.server.rest.server import ConanServer
from conans.server.crypto.jwt.jwt_credentials_manager import JWTCredentialsManager
from conans.server.crypto.jwt.jwt_updown_manager import JWTUpDownAuthManager
import os

from conans.server.conf import ConanServerConfigParser
from conans import __version__ as SERVER_VERSION
from conans.server.conf import MIN_CLIENT_COMPATIBLE_VERSION
from conans.model.version import Version
from conans.server.migrations import ServerMigrator
from conans.util.log import logger


def migrate_and_get_server_config(base_folder, storage_folder=None):
    server_config = ConanServerConfigParser(base_folder, storage_folder=storage_folder)

    if server_config.store_adapter == "disk":
        storage_path = server_config.disk_storage_path
    else:
        storage_path = None

    migrator = ServerMigrator(server_config.conan_folder, storage_path,
                              Version(SERVER_VERSION), logger)
    migrator.migrate()

    # Init again server_config, migrator could change something
    server_config = ConanServerConfigParser(base_folder, storage_folder=storage_folder)
    return server_config


class ServerLauncher(object):
    def __init__(self):
        user_folder = os.path.expanduser("~")

        server_config = migrate_and_get_server_config(user_folder)

        authorizer = BasicAuthorizer(server_config.read_permissions,
                                     server_config.write_permissions)
        authenticator = BasicAuthenticator(dict(server_config.users))

        credentials_manager = JWTCredentialsManager(server_config.jwt_secret,
                                                    server_config.jwt_expire_time)

        updown_auth_manager = JWTUpDownAuthManager(server_config.updown_secret,
                                                   server_config.authorize_timeout)

        file_manager = get_file_manager(server_config, updown_auth_manager=updown_auth_manager)

        self.ra = ConanServer(server_config.port, server_config.ssl_enabled,
                              credentials_manager, updown_auth_manager,
                              authorizer, authenticator, file_manager,
                              Version(SERVER_VERSION), Version(MIN_CLIENT_COMPATIBLE_VERSION))

    def launch(self):
        self.ra.run(host="0.0.0.0")


launcher = ServerLauncher()
app = launcher.ra.root_app


def main(*args):
    launcher.launch()


if __name__ == "__main__":
    main()
