from conans.migrations import Migrator
from conans.model.version import Version
from conans.util.files import rmdir
from conans.server.conf import ConanServerConfigParser

class ServerMigrator(Migrator):

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############

        # VERSION 0.1
        if old_version == Version("0.1"):
            # Remove config, conans, all!
            self.out.warn("Reseting configuration and storage files...")
            if self.conf_path:
                rmdir(self.conf_path)
            if self.store_path:
                rmdir(self.store_path)
        # VERSION 0.19
        if old_version < Version("0.19.1"):
            self.out.warn("Upgrading to new authentication middleware ...")
            config = ConanServerConfigParser(self.base_folder)
            config.read(config.config_filename)
            config.set("server", "authentication", "basic")
            config.set("server", "htpasswd_file", "")
            with open(config.config_filename) as fp:
                config.write(fp)

        # ########################################################################
