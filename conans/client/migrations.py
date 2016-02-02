from conans.migrations import Migrator
from conans.util.files import rmdir, load, save
from conans.model.version import Version
import os
from conans.client.conf import default_settings_yml


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
        elif old_version < Version("0.5"):
            self.out.warn("Migration: Updating settings.yml with new gcc versions")
            default_settings = load(self.paths.settings_path)
            default_settings = default_settings.replace(
                                    'version: ["4.6", "4.7", "4.8", "4.9", "5.0"]',
                                    'version: ["4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3"]')
            save(self.paths.settings_path, default_settings)
        elif old_version < Version("0.7"):
            self.out.warn("Migration: Updating settings.yml")
            old_settings = """
os: [Windows, Linux, Macos, Android]
arch: [x86, x86_64, armv]
compiler:
    gcc:
        version: ["4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3"]
    Visual Studio:
        runtime: [None, MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7"]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0"]

build_type: [None, Debug, Release]
"""
            current_settings = load(self.paths.settings_path)
            if current_settings != old_settings:
                backup_path = self.paths.settings_path + ".backup"
                save(backup_path, current_settings)
                self.out.warn("*" * 40)
                self.out.warn("A new settings.yml has been defined")
                self.out.warn("Your old settings.yml has been backup'd to: %s" % backup_path)
                self.out.warn("*" * 40)
            save(self.paths.settings_path, default_settings_yml)
