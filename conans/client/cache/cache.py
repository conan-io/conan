import os
import platform
from typing import List

from jinja2 import Template


from conan.internal.cache.cache import DataCache, RecipeLayout, PackageLayout
from conans.client.cache.editable import EditablePackages
from conans.client.cache.remote_registry import RemoteRegistry
from conans.client.conf import default_settings_yml
from conans.client.store.localdb import LocalDB
from conans.model.conf import ConfDefinition
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.model.settings import Settings
from conans.paths import DEFAULT_PROFILE_NAME
from conans.util.files import load, save, mkdir


CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REMOTES = "remotes.json"
PROFILES_FOLDER = "profiles"
EXTENSIONS_FOLDER = "extensions"
HOOKS_EXTENSION_FOLDER = "hooks"
PLUGINS_FOLDER = "plugins"
DEPLOYERS_EXTENSION_FOLDER = "deploy"
CUSTOM_COMMANDS_FOLDER = "commands"


# TODO: Rename this to ClientHome
class ClientCache(object):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, cache_folder):
        self.cache_folder = cache_folder

        # Caching
        self._config = None
        self._new_config = None
        self.editable_packages = EditablePackages(self.cache_folder)
        # paths
        self._store_folder = self.new_config.get("core.cache:storage_path") or \
                             os.path.join(self.cache_folder, "p")

        mkdir(self._store_folder)
        db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
        self._data_cache = DataCache(self._store_folder, db_filename)
        # The cache is first thing instantiated, we can remove this from env now
        self._localdb_encryption_key = os.environ.pop('CONAN_LOGIN_ENCRYPTION_KEY', None)

    def closedb(self):
        self._data_cache.closedb()

    def create_export_recipe_layout(self, ref: RecipeReference):
        return self._data_cache.create_export_recipe_layout(ref)

    def assign_rrev(self, layout: RecipeLayout):
        return self._data_cache.assign_rrev(layout)

    def create_build_pkg_layout(self, ref):
        return self._data_cache.create_build_pkg_layout(ref)

    def assign_prev(self, layout: PackageLayout):
        return self._data_cache.assign_prev(layout)

    def ref_layout(self, ref: RecipeReference):
        return self._data_cache.get_reference_layout(ref)

    def pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_package_layout(ref)

    def get_or_create_ref_layout(self, ref: RecipeReference):
        return self._data_cache.get_or_create_ref_layout(ref)

    def get_or_create_pkg_layout(self, ref: PkgReference):
        return self._data_cache.get_or_create_pkg_layout(ref)

    def remove_recipe_layout(self, layout):
        self._data_cache.remove_recipe(layout)

    def remove_package_layout(self, layout):
        self._data_cache.remove_package(layout)

    def get_recipe_timestamp(self, ref):
        return self._data_cache.get_recipe_timestamp(ref)

    def get_package_timestamp(self, ref):
        return self._data_cache.get_package_timestamp(ref)

    def update_recipe_timestamp(self, ref):
        """ when the recipe already exists in cache, but we get a new timestamp from a server
        that would affect its order in our cache """
        return self._data_cache.update_recipe_timestamp(ref)

    def all_refs(self):
        return self._data_cache.list_references()

    def exists_rrev(self, ref):
        # Used just by inspect to check before calling get_recipe()
        return self._data_cache.exists_rrev(ref)

    def exists_prev(self, pref):
        # Used just by download to skip downloads if prev already exists in cache
        return self._data_cache.exists_prev(pref)

    def get_package_revisions_references(self, pref: PkgReference, only_latest_prev=False):
        return self._data_cache.get_package_revisions_references(pref, only_latest_prev)

    def get_package_references(self, ref: RecipeReference,
                               only_latest_prev=True) -> List[PkgReference]:
        """Get the latest package references"""
        return self._data_cache.get_package_references(ref, only_latest_prev)

    def get_matching_build_id(self, ref, build_id):
        return self._data_cache.get_matching_build_id(ref, build_id)

    def get_recipe_revisions_references(self, ref, only_latest_rrev=False):
        return self._data_cache.get_recipe_revisions_references(ref, only_latest_rrev)

    def get_latest_recipe_reference(self, ref):
        return self._data_cache.get_latest_recipe_reference(ref)

    def get_latest_package_reference(self, pref):
        return self._data_cache.get_latest_package_reference(pref)

    @property
    def store(self):
        return self._store_folder

    @property
    def remotes_path(self):
        return os.path.join(self.cache_folder, REMOTES)

    @property
    def remotes_registry(self) -> RemoteRegistry:
        return RemoteRegistry(self)

    @property
    def new_config_path(self):
        return os.path.join(self.cache_folder, "global.conf")

    @property
    def new_config(self):
        """ this is the new global.conf to replace the old conan.conf that contains
        configuration defined with the new syntax as in profiles, this config will be composed
        to the profile ones and passed to the conanfiles.conf, which can be passed to collaborators
        """
        if self._new_config is None:
            self._new_config = ConfDefinition()
            if os.path.exists(self.new_config_path):
                text = load(self.new_config_path)
                distro = None
                if platform.system() in ["Linux", "FreeBSD"]:
                    import distro
                content = Template(text).render({"platform": platform, "os": os, "distro": distro})
                self._new_config.loads(content)
        return self._new_config

    @property
    def localdb(self):
        localdb_filename = os.path.join(self.cache_folder, LOCALDB)
        return LocalDB.create(localdb_filename, encryption_key=self._localdb_encryption_key)

    @property
    def profiles_path(self):
        return os.path.join(self.cache_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return os.path.join(self.cache_folder, CONAN_SETTINGS)

    @property
    def custom_commands_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, CUSTOM_COMMANDS_FOLDER)

    @property
    def plugins_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, PLUGINS_FOLDER)

    @property
    def default_profile_path(self):
        # Used only in testing, and this class "reset_default_profile"
        return os.path.join(self.cache_folder, PROFILES_FOLDER, DEFAULT_PROFILE_NAME)

    @property
    def hooks_path(self):
        """
        :return: Hooks folder in client cache
        """
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, HOOKS_EXTENSION_FOLDER)

    @property
    def deployers_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, DEPLOYERS_EXTENSION_FOLDER)

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""
        self.initialize_settings()
        content = load(self.settings_path)
        return Settings.loads(content)

    def initialize_settings(self):
        # TODO: This is called by ConfigAPI.init(), maybe move everything there?
        if not os.path.exists(self.settings_path):
            settings_yml = default_settings_yml
            save(self.settings_path, settings_yml)
            save(self.settings_path + ".orig", settings_yml)  # stores a copy, to check migrations
