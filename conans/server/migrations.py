from conans.migrations import Migrator


class ServerMigrator(Migrator):

    def __init__(self, conf_path, store_path, current_version, force_migrations):
        self.force_migrations = force_migrations
        self.store_path = store_path
        super(ServerMigrator, self).__init__(conf_path, current_version)
