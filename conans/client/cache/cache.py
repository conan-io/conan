import os
import platform
import textwrap
from typing import List

import yaml
from jinja2 import FileSystemLoader, Environment

from conan import conan_version
from conan.api.output import ConanOutput
from conan.internal.api import detect_api
from conan.internal.cache.cache import DataCache, RecipeLayout, PackageLayout
from conans.client.cache.editable import EditablePackages
from conans.client.cache.remote_registry import RemoteRegistry
from conans.client.conf import default_settings_yml
from conans.client.store.localdb import LocalDB
from conans.errors import ConanException
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


# TODO: Rename this to ClientHome
class ClientCache(object):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, cache_folder):
        self.cache_folder = cache_folder

        # Caching
        self._new_config = None
        self.editable_packages = EditablePackages(self.cache_folder)
        # paths
        self._store_folder = self.new_config.get("core.cache:storage_path") or \
                             os.path.join(self.cache_folder, "p")

        try:
            mkdir(self._store_folder)
            db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
            self._data_cache = DataCache(self._store_folder, db_filename)
        except Exception as e:
            raise ConanException(f"Couldn't initialize storage in {self._store_folder}: {e}")

    @property
    def temp_folder(self):
        """ temporary folder where Conan puts exports and packages before the final revision
        is computed"""
        # TODO: Improve the path definitions, this is very hardcoded
        return os.path.join(self.cache_folder, "p", "t")

    @property
    def builds_folder(self):
        return os.path.join(self.cache_folder, "p", "b")

    def create_export_recipe_layout(self, ref: RecipeReference):
        return self._data_cache.create_export_recipe_layout(ref)

    def assign_rrev(self, layout: RecipeLayout):
        return self._data_cache.assign_rrev(layout)

    def create_build_pkg_layout(self, ref):
        return self._data_cache.create_build_pkg_layout(ref)

    def assign_prev(self, layout: PackageLayout):
        return self._data_cache.assign_prev(layout)

    # Recipe methods
    def recipe_layout(self, ref: RecipeReference):
        return self._data_cache.get_recipe_layout(ref)

    def get_latest_recipe_reference(self, ref):
        # TODO: We keep this for testing only, to be removed
        assert ref.revision is None
        return self._data_cache.get_recipe_layout(ref).reference

    def get_recipe_revisions_references(self, ref):
        # For listing multiple revisions only
        assert ref.revision is None
        return self._data_cache.get_recipe_revisions_references(ref)

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

    def remove_build_id(self, pref):
        self._data_cache.remove_build_id(pref)

    def update_recipe_timestamp(self, ref):
        """ when the recipe already exists in cache, but we get a new timestamp from a server
        that would affect its order in our cache """
        return self._data_cache.update_recipe_timestamp(ref)

    def all_refs(self):
        return self._data_cache.list_references()

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

    def get_latest_package_reference(self, pref):
        return self._data_cache.get_latest_package_reference(pref)

    @property
    def store(self):
        return self._store_folder

    @property
    def default_sources_backup_folder(self):
        return os.path.join(self.cache_folder, "sources")

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
                template = Environment(loader=FileSystemLoader(self.cache_folder)).from_string(text)
                content = template.render({"platform": platform, "os": os, "distro": distro,
                                           "conan_version": conan_version,
                                           "conan_home_folder": self.cache_folder,
                                           "detect_api": detect_api})
                self._new_config.loads(content)
            else:  # creation of a blank global.conf file for user convenience
                default_global_conf = textwrap.dedent("""\
                    # Core configuration (type 'conan config list' to list possible values)
                    # e.g, for CI systems, to raise if user input would block
                    # core:non_interactive = True
                    # some tools.xxx config also possible, though generally better in profiles
                    # tools.android:ndk_path = my/path/to/android/ndk
                    """)
                save(self.new_config_path, default_global_conf)
        return self._new_config

    @property
    def localdb(self):
        localdb_filename = os.path.join(self.cache_folder, LOCALDB)
        return LocalDB.create(localdb_filename)

    @property
    def profiles_path(self):
        return os.path.join(self.cache_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return os.path.join(self.cache_folder, CONAN_SETTINGS)

    @property
    def custom_commands_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, "commands")

    @property
    def custom_generators_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, "generators")

    @property
    def plugins_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, PLUGINS_FOLDER)

    @property
    def default_profile_path(self):
        # Used only in testing, and this class "reset_default_profile"
        return os.path.join(self.cache_folder, PROFILES_FOLDER, DEFAULT_PROFILE_NAME)

    @property
    def hooks_path(self):
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, HOOKS_EXTENSION_FOLDER)

    @property
    def deployers_path(self):
        deploy = os.path.join(self.cache_folder, EXTENSIONS_FOLDER, "deploy")
        if os.path.exists(deploy):
            ConanOutput().warning("Use 'deployers' cache folder for deployers instead of 'deploy'",
                                  warn_tag="deprecated")
            return deploy
        return os.path.join(self.cache_folder, EXTENSIONS_FOLDER, "deployers")

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""
        self.initialize_settings()

        def _load_settings(path):
            try:
                return yaml.safe_load(load(path)) or {}
            except yaml.YAMLError as ye:
                raise ConanException("Invalid settings.yml format: {}".format(ye))

        settings = _load_settings(self.settings_path)
        user_settings_file = os.path.join(self.cache_folder, "settings_user.yml")
        if os.path.exists(user_settings_file):
            settings_user = _load_settings(user_settings_file)

            def appending_recursive_dict_update(d, u):
                # Not the same behavior as conandata_update, because this append lists
                for k, v in u.items():
                    if isinstance(v, list):
                        current = d.get(k) or []
                        d[k] = current + [value for value in v if value not in current]
                    elif isinstance(v, dict):
                        current = d.get(k) or {}
                        if isinstance(current, list):  # convert to dict lists
                            current = {k: None for k in current}
                        d[k] = appending_recursive_dict_update(current, v)
                    else:
                        d[k] = v
                return d

            appending_recursive_dict_update(settings, settings_user)

        return Settings(settings)

    def initialize_settings(self):
        # TODO: This is called by ConfigAPI.init(), maybe move everything there?
        if not os.path.exists(self.settings_path):
            settings_yml = default_settings_yml
            save(self.settings_path, settings_yml)
            save(self.settings_path + ".orig", settings_yml)  # stores a copy, to check migrations
