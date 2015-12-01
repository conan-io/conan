from conans.migrations import Migrator
from conans.util.files import rmdir
from conans.model.version import Version
import os


class ClientMigrator(Migrator):

    def __init__(self, paths, current_version, out):
        self.paths = paths
        super(ClientMigrator, self).__init__(paths.conan_folder, paths.store,
                                             current_version, out)

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############
        # VERSION 0.1
        if old_version is None:
            return
        if old_version < Version("0.3"):
            self.out.warn("Migration: Reseting configuration and storage files...")
            if os.path.exists(self.conf_path):
                rmdir(self.conf_path)
            if os.path.exists(self.store_path):
                rmdir(self.store_path)
