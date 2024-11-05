from conan import conan_version
from conans.server.conf import ConanServerConfigParser
from conans.server.migrations import ServerMigrator


def migrate_and_get_server_config(base_folder, force_migration=False, is_custom_path=False):
    server_config = ConanServerConfigParser(base_folder, is_custom_path=is_custom_path)
    storage_path = server_config.disk_storage_path
    migrator = ServerMigrator(server_config.conan_folder, storage_path,
                              conan_version, force_migration)
    migrator.migrate()

    # Init again server_config, migrator could change something
    server_config = ConanServerConfigParser(base_folder, is_custom_path=is_custom_path)
    return server_config
