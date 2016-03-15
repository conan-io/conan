from conans.migrations import Migrator
from conans.util.files import rmdir, load, save
from conans.model.version import Version
import os
from conans.client.conf import default_settings_yml
from conans.server.store.disk_adapter import DiskAdapter
from conans.server.store.file_manager import FileManager


class ClientMigrator(Migrator):

    def __init__(self, paths, current_version, out, manager):
        self.paths = paths
        self.manager = manager
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
        elif old_version < Version("0.8"):
            self.out.info("**** Migrating to conan 0.8 *****")
            settings_backup_path = self.paths.settings_path + ".backup"
            save(settings_backup_path, load(self.paths.settings_path))
            # Save new settings
            save(self.paths.settings_path, default_settings_yml)
            self.out.info("- A new settings.yml has been defined")
            self.out.info("  Your old file has been backup'd to: %s" % settings_backup_path)

            old_conanconf = load(self.paths.conan_conf_path)
            conf = dict(self.paths.conan_config.get_conf("settings_defaults"))
            if conf.get("os", None) in ("Linux", "Macos") and \
               conf.get("compiler", None) in ("gcc", "clang", "apple-clang"):

                # Backup the old config and append the new setting
                config_backup_path = self.paths.conan_conf_path + ".backup"
                save(config_backup_path, old_conanconf)
                new_setting = "libstdc++"
                if conf.get("compiler", None) == "apple-clang":
                    new_setting = "libc++"
                self.paths.conan_config.set("settings_defaults", "compiler.libcxx", new_setting)
                with open(self.paths.conan_conf_path, 'wb') as configfile:
                    self.paths.conan_config.write(configfile)

                self.out.info("- A new conan.conf has been defined")
                self.out.info("  Your old file has been backup'd to: %s" % config_backup_path)

                self.out.info("- Reseting storage files...")
                if os.path.exists(self.store_path):
                    rmdir(self.store_path)

                # Print information about new setting
                self.out.warn("{0:s} IMPORTANT {0:s}".format("*" * 30))
                self.out.warn("Conan 0.8 have a new setting for your compiler: 'compiler.libcxx' ")
                self.out.warn("It defines the Standard C++ Library and it's ABI (C99 or C++11)")
                if new_setting == "libstdc++":
                    self.out.warn("By default, and to keep the higher compatibility in your packages, we setted this setting value to 'libstdc++'")
                    self.out.warn("If you are using C++11 features or you want to use the gcc>5.1 ABI, set this setting to 'libstdc++11' ")
                self.out.warn("If you uploaded some packages it's needed that you regenerate them, conan will set the new setting automatically")
                self.out.warn("If your packages are written in pure 'C' language, you should deactivate this setting for your package adding this line to your conanfile.py config method:")
                self.out.info(" ")
                self.out.info(" def config(self):")
                self.out.info("     del self.settings.compiler.libcxx")
                self.out.info(" ")
                self.out.warn("Your local storage has been deleted, perform a 'conan install' in your projects to restore them.")
                self.out.warn("You can read more information about this new setting and how to adapt your packages here: http://blog.conan.io/")
                self.out.warn("*" * 71)
                self.out.info("   ")
