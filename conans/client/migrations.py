from conans.migrations import Migrator


class ClientMigrator(Migrator):

    def __init__(self, cache_folder, current_version):
        self.cache_folder = cache_folder
        super(ClientMigrator, self).__init__(cache_folder, current_version)
