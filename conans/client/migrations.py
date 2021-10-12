import os
import shutil

import six

from conans import DEFAULT_REVISION_V1
from conans.client import migrations_settings
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import migrate_registry_file
from conans.client.conf.config_installer import _ConfigOrigin, _save_configs
from conans.client.rest.cacert import cacert_default, cacert
from conans.client.tools import replace_in_file
from conans.errors import ConanException
from conans.migrations import Migrator
from conans.model.manifest import FileTreeManifest
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.version import Version
from conans.paths import CONANFILE, EXPORT_SOURCES_TGZ_NAME, PACKAGE_TGZ_NAME, EXPORT_TGZ_NAME, \
    CACERT_FILE
from conans.paths import PACKAGE_METADATA
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.util.files import list_folder_subdirs, load, save


class ClientMigrator(Migrator):

    def __init__(self, cache_folder, current_version, out):
        self.cache_folder = cache_folder
        super(ClientMigrator, self).__init__(cache_folder, current_version, out)

    def _update_settings_yml(self, cache, old_version):

        from conans.client.conf import get_default_settings_yml
        settings_path = cache.settings_path
        if not os.path.exists(settings_path):
            self.out.warn("Migration: This conan installation doesn't have settings yet")
            self.out.warn("Nothing to migrate here, settings will be generated automatically")
            return

        var_name = "settings_{}".format(old_version.replace(".", "_"))

        def save_new():
            new_path = cache.settings_path + ".new"
            save(new_path, get_default_settings_yml())
            self.out.warn("*" * 40)
            self.out.warn("settings.yml is locally modified, can't be updated")
            self.out.warn("The new settings.yml has been stored in: %s" % new_path)
            self.out.warn("*" * 40)

        self.out.warn("Migration: Updating settings.yml")
        if hasattr(migrations_settings, var_name):
            version_default_contents = getattr(migrations_settings, var_name)
            if version_default_contents.splitlines() != get_default_settings_yml().splitlines():
                current_settings = load(cache.settings_path)
                if current_settings != version_default_contents:
                    save_new()
                else:
                    save(cache.settings_path, get_default_settings_yml())
            else:
                self.out.info("Migration: Settings already up to date")
        else:
            # We don't have the value for that version, so don't override
            save_new()

    def _make_migrations(self, old_version):
        # ############### FILL THIS METHOD WITH THE REQUIRED ACTIONS ##############
        # VERSION 0.1
        if old_version is None:
            return

        # Migrate the settings if they were the default for that version
        cache = ClientCache(self.cache_folder, self.out)
        self._update_settings_yml(cache, old_version)

        if old_version < Version("1.0"):
            _migrate_lock_files(cache, self.out)

        if old_version < Version("1.12.0"):
            migrate_plugins_to_hooks(cache)

        if old_version < Version("1.13.0"):
            # MIGRATE LOCAL CACHE TO GENERATE MISSING METADATA.json
            _migrate_create_metadata(cache, self.out)

        if old_version < Version("1.14.0"):
            migrate_config_install(cache)

        if old_version < Version("1.14.2"):
            _migrate_full_metadata(cache, self.out)

        if old_version < Version("1.15.0"):
            migrate_registry_file(cache, self.out)

        if old_version < Version("1.19.0"):
            migrate_localdb_refresh_token(cache, self.out)

        if old_version < Version("1.26.0"):
            migrate_editables_use_conanfile_name(cache)

        if old_version < Version("1.31.0"):
            migrate_tgz_location(cache, self.out)

        if old_version < Version("1.40.3"):
            remove_buggy_cacert(cache, self.out)


def _get_refs(cache):
    folders = list_folder_subdirs(cache.store, 4)
    return [ConanFileReference(*s.split("/")) for s in folders]


def _get_prefs(layout):
    packages_folder = layout.packages()
    folders = list_folder_subdirs(packages_folder, 1)
    return [PackageReference(layout.ref, s) for s in folders]


def remove_buggy_cacert(cache, out):
    """https://github.com/conan-io/conan/pull/9696
    Needed migration because otherwise the cacert is kept in the cache even upgrading conan"""
    cacert_path = os.path.join(cache.cache_folder, CACERT_FILE)
    if os.path.exists(cacert_path):
        current_cacert = load(cacert_path).encode('utf-8') if six.PY2 else load(cacert_path)
        if current_cacert == cacert_default:
            out.info("Removing the 'cacert.pem' file...")
            os.unlink(cacert_path)
        elif current_cacert != cacert:  # locally modified by user
            new_path = cacert_path + ".new"
            save(new_path, cacert)
            out.warn("*" * 40)
            out.warn("'cacert.pem' is locally modified, can't be updated")
            out.warn("The new 'cacert.pem' has been stored in: %s" % new_path)
            out.warn("*" * 40)
        else:
            out.info("Conan 'cacert.pem' is up to date...")


def migrate_tgz_location(cache, out):
    """ In Conan 1.31, the temporary .tgz are no longer stored in the content folders. In case
    they are found there, they can be removed, and the next time they are needed (upload), they
    will be compressed again
    """
    out.info("Removing temporary .tgz files, they are stored in a different location now")
    refs = _get_refs(cache)
    for ref in refs:
        try:
            base_folder = os.path.normpath(os.path.join(cache.store, ref.dir_repr()))
            for d, _, fs in os.walk(base_folder):
                for f in fs:
                    if f in (EXPORT_SOURCES_TGZ_NAME, EXPORT_TGZ_NAME, PACKAGE_TGZ_NAME):
                        tgz_file = os.path.join(d, f)
                        os.remove(tgz_file)
        except Exception as e:
            raise ConanException("Something went wrong while removing temporary .tgz files "
                                 "in the cache, please try to fix the issue or wipe the cache: {}"
                                 ":{}".format(ref, e))


def migrate_localdb_refresh_token(cache, out):
    from sqlite3 import OperationalError

    with cache.localdb._connect() as connection:
        try:
            statement = connection.cursor()
            statement.execute("ALTER TABLE users_remotes ADD refresh_token TEXT;")
        except OperationalError:
            # This likely means the column is already there (fresh created table)
            # In the worst scenario the user will be requested to remove the file by hand
            pass


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
            metadata_path = layout.package_metadata()
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


def migrate_plugins_to_hooks(cache, output=None):
    plugins_path = os.path.join(cache.cache_folder, "plugins")
    if os.path.exists(plugins_path) and not os.path.exists(cache.hooks_path):
        os.rename(plugins_path, cache.hooks_path)
    conf_path = cache.conan_conf_path
    replace_in_file(conf_path, "[plugins]", "[hooks]", strict=False, output=output)


def migrate_editables_use_conanfile_name(cache):
    """
    In Conan v1.26 we store full path to the conanfile in the editable_package.json file, before
    it Conan was storing just the directory and assume that the 'conanfile' was a file
    named 'conanfile.py' inside that folder
    """
    for ref, data in cache.editable_packages.edited_refs.items():
        path = data["path"]
        if os.path.isdir(path):
            path = os.path.join(path, CONANFILE)
        cache.editable_packages.add(ref, path, layout=data["layout"])
