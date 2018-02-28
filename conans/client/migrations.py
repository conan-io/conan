import os
import shutil

from conans.client.client_cache import CONAN_CONF, PROFILES_FOLDER
from conans.migrations import Migrator
from conans.paths import EXPORT_SOURCES_DIR_OLD
from conans.util.files import load, save, list_folder_subdirs
from conans.model.version import Version
from conans.errors import ConanException


class ClientMigrator(Migrator):

    def __init__(self, client_cache, current_version, out):
        self.client_cache = client_cache
        super(ClientMigrator, self).__init__(client_cache.conan_folder, client_cache.store,
                                             current_version, out)

    def _update_settings_yml(self, old_settings):
        from conans.client.conf import default_settings_yml
        settings_path = self.client_cache.settings_path
        if not os.path.exists(settings_path):
            self.out.warn("Migration: This conan installation doesn't have settings yet")
            self.out.warn("Nothing to migrate here, settings will be generated automatically")
            return

        current_settings = load(self.client_cache.settings_path)
        if current_settings != default_settings_yml:
            self.out.warn("Migration: Updating settings.yml")
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
        if old_version < Version("1.1.0-dev"):
            old_settings = """
# Only for cross building, 'os_build/arch_build' is the system that runs Conan
os_build: [Windows, WindowsStore, Linux, Macos, FreeBSD, SunOS]
arch_build: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8, sparc, sparcv9, mips, mips64, avr, armv7s, armv7k]

# Only for building cross compilation tools, 'os_target/arch_target' is the system for
# which the tools generate code
os_target: [Windows, Linux, Macos, Android, iOS, watchOS, tvOS, FreeBSD, SunOS, Arduino]
arch_target: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8, sparc, sparcv9, mips, mips64, avr, armv7s, armv7k]

# Rest of the settings are "host" settings:
# - For native building/cross building: Where the library/program will run.
# - For building cross compilation tools: Where the cross compiler will run.
os:
    Windows:
        subsystem: [None, cygwin, msys, msys2, wsl]
    WindowsStore:
        version: ["8.1", "10.0"]
    Linux:
    Macos:
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3", "11.0"]
    watchOS:
        version: ["4.0"]
    tvOS:
        version: ["11.0"]
    FreeBSD:
    SunOS:
    Arduino:
        board: ANY
arch: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8, sparc, sparcv9, mips, mips64, avr, armv7s, armv7k]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
        threads: [None, posix]
        libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                  "5", "5.1", "5.2", "5.3", "5.4",
                  "6", "6.1", "6.2", "6.3", "6.4",
                  "7", "7.1", "7.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15"]
        toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp, v140, v140_xp, v140_clang_c2, LLVM-vs2014, LLVM-vs2014_xp, v141, v141_xp, v141_clang_c2]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0", "5.0"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""
            self._update_settings_yml(old_settings)

        if old_version < Version("1.0"):
            _migrate_lock_files(self.client_cache, self.out)

        if old_version < Version("0.25"):
            from conans.paths import DEFAULT_PROFILE_NAME
            default_profile_path = os.path.join(self.client_cache.conan_folder, PROFILES_FOLDER,
                                                DEFAULT_PROFILE_NAME)
            if not os.path.exists(default_profile_path):
                self.out.warn("Migration: Moving default settings from %s file to %s"
                              % (CONAN_CONF, DEFAULT_PROFILE_NAME))
                conf_path = os.path.join(self.client_cache.conan_folder, CONAN_CONF)

                migrate_to_default_profile(conf_path, default_profile_path)

                self.out.warn("Migration: export_source cache new layout")
                migrate_c_src_export_source(self.client_cache, self.out)


def _add_build_cross_settings(client_cache, out):
    out.warn("Migration: Adding `os_build` and `arch_build` to default settings")
    try:
        default_profile = client_cache.default_profile
        default_profile.settings["arch_build"] = default_profile.settings["arch"]
        default_profile.settings["os_build"] = default_profile.settings["os"]
        save(client_cache.default_profile_path, default_profile.dumps())
    except Exception:
        out.error("Something went wrong adding 'os_build' and 'arch_build' to your default."
                  " You can add it manually adjusting them with the same value as 'os' and 'arch'")


def _migrate_lock_files(client_cache, out):
    out.warn("Migration: Removing old lock files")
    base_dir = client_cache.store
    pkgs = list_folder_subdirs(base_dir, 4)
    for pkg in pkgs:
        out.info("Removing locks for %s" % pkg)
        try:
            count = os.path.join(base_dir, pkg, "rw.count")
            if os.path.exists(count):
                os.remove(count)
            count = os.path.join(base_dir, pkg, "rw.count.lock")
            if os.path.exists(count):
                os.remove(count)
            locks = os.path.join(base_dir, pkg, "locks")
            if os.path.exists(locks):
                shutil.rmtree(locks)
        except Exception as e:
            raise ConanException("Something went wrong while removing %s locks\n"
                                 "Error: %s\n"
                                 "Please clean your local conan cache manually"
                                 % (pkg, str(e)))
    out.warn("Migration: Removing old lock files finished\n")


def migrate_to_default_profile(conf_path, default_profile_path):
    tag = "[settings_defaults]"
    old_conf = load(conf_path)
    if tag not in old_conf:
        return
    tmp = old_conf.find(tag)
    new_conf = old_conf[0:tmp]
    rest = old_conf[tmp + len(tag):]
    if tmp:
        if "]" in rest:  # More sections after the settings_defaults
            new_conf += rest[rest.find("["):]
            save(conf_path, new_conf)
            settings = rest[:rest.find("[")].strip()
        else:
            save(conf_path, new_conf)
            settings = rest.strip()
        # Now generate the default profile from the read settings_defaults
        new_profile = "[settings]\n%s" % settings
        save(default_profile_path, new_profile)


def migrate_c_src_export_source(client_cache, out):
    from conans.util.files import list_folder_subdirs
    package_folders = list_folder_subdirs(client_cache.store, 4)
    for package in package_folders:
        package_folder = os.path.join(client_cache.store, package)
        c_src = os.path.join(package_folder, "export/%s" % EXPORT_SOURCES_DIR_OLD)
        if os.path.exists(c_src):
            out.warn("Migration: Removing package with old export_sources layout: %s" % package)
            try:
                shutil.rmtree(package_folder)
            except Exception:
                out.warn("Migration: Can't remove the '%s' directory, "
                         "remove it manually" % package_folder)
