from conans.server.conf import ConanServerConfigParser
from conans.server.migrations import ServerMigrator
from conans.util.log import logger
from conans.model.version import Version
from conans import __version__ as SERVER_VERSION


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
