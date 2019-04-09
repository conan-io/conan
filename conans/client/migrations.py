import os
import shutil

from conans import DEFAULT_REVISION_V1
from conans.client.cache.cache import CONAN_CONF, PROFILES_FOLDER
from conans.client.conf.config_installer import _ConfigOrigin, _save_configs
from conans.client.tools import replace_in_file
from conans.errors import ConanException
from conans.migrations import Migrator
from conans.model.manifest import FileTreeManifest
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.version import Version
from conans.paths import EXPORT_SOURCES_DIR_OLD
from conans.paths import PACKAGE_METADATA
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.util.files import list_folder_subdirs, load, save


class ClientMigrator(Migrator):

    def __init__(self, cache, current_version, out):
        self.cache = cache
        super(ClientMigrator, self).__init__(cache.conan_folder, cache.store,
                                             current_version, out)

    def _update_settings_yml(self, old_settings):
        from conans.client.conf import default_settings_yml
        settings_path = self.cache.settings_path
        if not os.path.exists(settings_path):
            self.out.warn("Migration: This conan installation doesn't have settings yet")
            self.out.warn("Nothing to migrate here, settings will be generated automatically")
            return

        current_settings = load(self.cache.settings_path)
        if current_settings != default_settings_yml:
            self.out.warn("Migration: Updating settings.yml")
            if current_settings != old_settings:
                new_path = self.cache.settings_path + ".new"
                save(new_path, default_settings_yml)
                self.out.warn("*" * 40)
                self.out.warn("settings.yml is locally modified, can't be updated")
                self.out.warn("The new settings.yml has been stored in: %s" % new_path)
                self.out.warn("*" * 40)
            else:
                save(self.cache.settings_path, default_settings_yml)

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############
        # VERSION 0.1
        if old_version is None:
            return

        if old_version < Version("0.25"):
            from conans.paths import DEFAULT_PROFILE_NAME
            default_profile_path = os.path.join(self.cache.conan_folder, PROFILES_FOLDER,
                                                DEFAULT_PROFILE_NAME)
            if not os.path.exists(default_profile_path):
                self.out.warn("Migration: Moving default settings from %s file to %s"
                              % (CONAN_CONF, DEFAULT_PROFILE_NAME))
                conf_path = os.path.join(self.cache.conan_folder, CONAN_CONF)

                migrate_to_default_profile(conf_path, default_profile_path)

                self.out.warn("Migration: export_source cache new layout")
                migrate_c_src_export_source(self.cache, self.out)

        if old_version < Version("1.0"):
            _migrate_lock_files(self.cache, self.out)

        if old_version < Version("1.12.0"):
            migrate_plugins_to_hooks(self.cache)

        if old_version < Version("1.13.0"):
            old_settings = """
# Only for cross building, 'os_build/arch_build' is the system that runs Conan
os_build: [Windows, WindowsStore, Linux, Macos, FreeBSD, SunOS]
arch_build: [x86, x86_64, ppc32, ppc64le, ppc64, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr]

# Only for building cross compilation tools, 'os_target/arch_target' is the system for
# which the tools generate code
os_target: [Windows, Linux, Macos, Android, iOS, watchOS, tvOS, FreeBSD, SunOS, Arduino]
arch_target: [x86, x86_64, ppc32, ppc64le, ppc64, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr]

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
        version: [None, "10.6", "10.7", "10.8", "10.9", "10.10", "10.11", "10.12", "10.13", "10.14"]
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3", "11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1"]
    watchOS:
        version: ["4.0", "4.1", "4.2", "4.3", "5.0", "5.1"]
    tvOS:
        version: ["11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1"]
    FreeBSD:
    SunOS:
    Arduino:
        board: ANY
arch: [x86, x86_64, ppc32, ppc64le, ppc64, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
        threads: [None, posix]
        libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                  "5", "5.1", "5.2", "5.3", "5.4", "5.5",
                  "6", "6.1", "6.2", "6.3", "6.4",
                  "7", "7.1", "7.2", "7.3",
                  "8", "8.1", "8.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15"]
        toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp,
                  v140, v140_xp, v140_clang_c2, LLVM-vs2012, LLVM-vs2012_xp,
                  LLVM-vs2013, LLVM-vs2013_xp, LLVM-vs2014, LLVM-vs2014_xp,
                  LLVM-vs2017, LLVM-vs2017_xp, v141, v141_xp, v141_clang_c2]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0",
                  "5.0", "6.0", "7.0",
                  "8"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0", "9.1", "10.0"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release, RelWithDebInfo, MinSizeRel]
cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
"""
            self._update_settings_yml(old_settings)

            # MIGRATE LOCAL CACHE TO GENERATE MISSING METADATA.json
            _migrate_create_metadata(self.cache, self.out)

        if old_version < Version("1.14.0"):
            migrate_config_install(self.cache)

        if old_version < Version("1.14.2"):
            _migrate_full_metadata(self.cache, self.out)


def _get_refs(cache):
    folders = list_folder_subdirs(cache.store, 4)
    return [ConanFileReference(*s.split("/")) for s in folders]


def _get_prefs(layout):
    packages_folder = layout.packages()
    folders = list_folder_subdirs(packages_folder, 1)
    return [PackageReference(layout.ref, s) for s in folders]


def _migrate_full_metadata(cache, out):
    # Fix for https://github.com/conan-io/conan/issues/4898
    out.warn("Running a full revision metadata migration")
    refs = _get_refs(cache)
    for ref in refs:
        try:
            base_folder = os.path.normpath(os.path.join(cache.store, ref.dir_repr()))
            layout = PackageCacheLayout(base_folder=base_folder, ref=ref, short_paths=None,
                                        no_lock=True)
            with layout.update_metadata() as metadata:
                # Updating the RREV
                if metadata.recipe.revision is None:
                    out.warn("Package %s metadata had recipe revision None, migrating" % str(ref))
                    folder = layout.export()
                    try:
                        manifest = FileTreeManifest.load(folder)
                        rrev = manifest.summary_hash
                    except Exception:
                        rrev = DEFAULT_REVISION_V1
                    metadata.recipe.revision = rrev

                prefs = _get_prefs(layout)
                existing_ids = [pref.id for pref in prefs]
                for pkg_id in list(metadata.packages.keys()):
                    if pkg_id not in existing_ids:
                        out.warn("Package %s metadata had stalled package information %s, removing"
                                 % (str(ref), pkg_id))
                        del metadata.packages[pkg_id]
                # UPDATING PREVS
                for pref in prefs:
                    try:
                        pmanifest = FileTreeManifest.load(layout.package(pref))
                        prev = pmanifest.summary_hash
                    except Exception:
                        prev = DEFAULT_REVISION_V1
                    metadata.packages[pref.id].revision = prev
                    metadata.packages[pref.id].recipe_revision = metadata.recipe.revision

        except Exception as e:
            raise ConanException("Something went wrong while migrating metadata.json files "
                                 "in the cache, please try to fix the issue or wipe the cache: {}"
                                 ":{}".format(ref, e))


def _migrate_create_metadata(cache, out):
    out.warn("Migration: Generating missing metadata files")
    refs = _get_refs(cache)

    for ref in refs:
        try:
            base_folder = os.path.normpath(os.path.join(cache.store, ref.dir_repr()))
            # Force using a package cache layout for everything, we want to alter the cache,
            # not the editables
            layout = PackageCacheLayout(base_folder=base_folder, ref=ref, short_paths=False,
                                        no_lock=True)
            folder = layout.export()
            try:
                manifest = FileTreeManifest.load(folder)
                rrev = manifest.summary_hash
            except Exception:
                rrev = DEFAULT_REVISION_V1
            metadata_path = os.path.join(layout.conan(), PACKAGE_METADATA)
            if not os.path.exists(metadata_path):
                out.info("Creating {} for {}".format(PACKAGE_METADATA, ref))
                prefs = _get_prefs(layout)
                metadata = PackageMetadata()
                metadata.recipe.revision = rrev
                for pref in prefs:
                    try:
                        pmanifest = FileTreeManifest.load(layout.package(pref))
                        prev = pmanifest.summary_hash
                    except Exception:
                        prev = DEFAULT_REVISION_V1
                    metadata.packages[pref.id].revision = prev
                    metadata.packages[pref.id].recipe_revision = metadata.recipe.revision
                save(metadata_path, metadata.dumps())
        except Exception as e:
            raise ConanException("Something went wrong while generating the metadata.json files "
                                 "in the cache, please try to fix the issue or wipe the cache: {}"
                                 ":{}".format(ref, e))
    out.success("Migration: Generating missing metadata files finished OK!\n")


def _migrate_lock_files(cache, out):
    out.warn("Migration: Removing old lock files")
    base_dir = cache.store
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


def migrate_config_install(cache):
    try:
        item = cache.config.get_item("general.config_install")
        items = [r.strip() for r in item.split(",")]
        if len(items) == 4:
            config_type, uri, verify_ssl, args = items
        elif len(items) == 1:
            uri = items[0]
            verify_ssl = "True"
            args = "None"
            config_type = None
        else:
            raise Exception("I don't know how to migrate this config install: %s" % items)
        verify_ssl = "true" in verify_ssl.lower()
        args = None if "none" in args.lower() else args
        config = _ConfigOrigin.from_item(uri, config_type, verify_ssl, args, None, None)
        _save_configs(cache.config_install_file, [config])
        cache.config.rm_item("general.config_install")
    except ConanException:
        pass


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


def migrate_c_src_export_source(cache, out):
    package_folders = list_folder_subdirs(cache.store, 4)
    for package in package_folders:
        package_folder = os.path.join(cache.store, package)
        c_src = os.path.join(package_folder, "export/%s" % EXPORT_SOURCES_DIR_OLD)
        if os.path.exists(c_src):
            out.warn("Migration: Removing package with old export_sources layout: %s" % package)
            try:
                shutil.rmtree(package_folder)
            except Exception:
                out.warn("Migration: Can't remove the '%s' directory, "
                         "remove it manually" % package_folder)


def migrate_plugins_to_hooks(cache, output=None):
    plugins_path = os.path.join(cache.conan_folder, "plugins")
    if os.path.exists(plugins_path) and not os.path.exists(cache.hooks_path):
        os.rename(plugins_path, cache.hooks_path)
    conf_path = cache.conan_conf_path
    replace_in_file(conf_path, "[plugins]", "[hooks]", strict=False, output=output)
