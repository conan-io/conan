from conans.migrations import Migrator
from conans.util.files import load, save
from conans.model.version import Version
import os
from conans.client.conf import default_settings_yml


class ClientMigrator(Migrator):

    def __init__(self, client_cache, current_version, out, manager):
        self.client_cache = client_cache
        self.manager = manager
        super(ClientMigrator, self).__init__(client_cache.conan_folder, client_cache.store,
                                             current_version, out)

    def _update_settings_yml(self, old_settings):
        settings_path = self.client_cache.settings_path
        if not os.path.exists(settings_path):
            self.out.warn("Migration: This conan installation doesn't have settings yet")
            self.out.warn("Nothing to migrate here, settings will be generated automatically")
            return

        self.out.warn("Migration: Updating settings.yml")
        current_settings = load(self.client_cache.settings_path)
        if current_settings != old_settings:
            backup_path = self.client_cache.settings_path + ".backup"
            save(backup_path, current_settings)
            self.out.warn("*" * 40)
            self.out.warn("A new settings.yml has been defined")
            self.out.warn("Your old settings.yml has been backup'd to: %s" % backup_path)
            self.out.warn("*" * 40)
        save(self.client_cache.settings_path, default_settings_yml)

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############
        # VERSION 0.1
        if old_version is None:
            return

        if old_version < Version("0.16"):
            old_settings = """
os: [Windows, Linux, Macos, Android, iOS]
arch: [x86, x86_64, ppc64le, armv6, armv7, armv7hf, armv8]
compiler:
    gcc:
        version: ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""
            self._update_settings_yml(old_settings)
