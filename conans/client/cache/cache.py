import os
import shutil
from collections import OrderedDict
from io import StringIO
from typing import List
from jinja2 import Environment, select_autoescape, FileSystemLoader, ChoiceLoader

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
from conan.cache.conan_reference_layout import RecipeLayout, PackageLayout
from conans.assets.templates import dict_loader
from conans.client.cache.editable import EditablePackages
from conans.client.cache.remote_registry import RemoteRegistry
from conans.client.conf import ConanClientConfigParser, get_default_client_conf, \
    get_default_settings_yml
from conans.client.conf.detect import detect_defaults_settings
from conans.client.output import Color
from conans.client.profile_loader import read_profile
from conans.client.store.localdb import LocalDB
from conans.errors import ConanException
from conans.model.conf import ConfDefinition
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference, PackageReference
from conans.model.settings import Settings
from conans.paths import ARTIFACTS_PROPERTIES_FILE
from conans.util.files import list_folder_subdirs, load, normalize, save, remove, mkdir
from conans.util.locks import Lock

CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REMOTES = "remotes.json"
PROFILES_FOLDER = "profiles"
HOOKS_FOLDER = "hooks"
TEMPLATES_FOLDER = "templates"
GENERATORS_FOLDER = "generators"


class ClientCache(object):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, cache_folder, output):
        self.cache_folder = cache_folder
        self._output = output

        # Caching
        self._no_lock = None
        self._config = None
        self._new_config = None
        self.editable_packages = EditablePackages(self.cache_folder)
        # paths
        self._store_folder = self.config.storage_path or os.path.join(self.cache_folder, "data")

        mkdir(self._store_folder)
        db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
        self._data_cache = DataCache(self._store_folder, db_filename)

    def closedb(self):
        self._data_cache.closedb()

    def update_reference(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_remote=None, new_timestamp=None, new_build_id=None):
        new_ref = ConanReference(new_ref) if new_ref else None
        return self._data_cache.update_reference(ConanReference(old_ref), new_ref, new_path,
                                                 new_remote, new_timestamp, new_build_id)

    def dump(self):
        out = StringIO()
        self._data_cache.dump(out)
        return out.getvalue()

    def assign_rrev(self, layout: RecipeLayout, ref: ConanReference):
        return self._data_cache.assign_rrev(layout, ref)

    def assign_prev(self, layout: PackageLayout, ref: ConanReference):
        return self._data_cache.assign_prev(layout, ref)

    def ref_layout(self, ref):
        return self._data_cache.get_reference_layout(ConanReference(ref))

    def pkg_layout(self, ref):
        return self._data_cache.get_package_layout(ConanReference(ref))

    def create_ref_layout(self, ref):
        return self._data_cache.create_reference_layout(ConanReference(ref))

    def create_pkg_layout(self, ref):
        return self._data_cache.create_package_layout(ConanReference(ref))

    def create_temp_ref_layout(self, ref):
        return self._data_cache.create_tmp_reference_layout(ConanReference(ref))

    def create_temp_pkg_layout(self, ref):
        return self._data_cache.create_tmp_package_layout(ConanReference(ref))

    def get_or_create_ref_layout(self, ref: ConanReference):
        return self._data_cache.get_or_create_reference_layout(ConanReference(ref))

    def get_or_create_pkg_layout(self, ref: ConanReference):
        return self._data_cache.get_or_create_package_layout(ConanReference(ref))

    def remove_layout(self, layout):
        layout.remove()
        self._data_cache.remove(ConanReference(layout.reference))

    def get_remote(self, ref):
        return self._data_cache.get_remote(ConanReference(ref))

    def set_remote(self, ref, remote):
        return self._data_cache.set_remote(ConanReference(ref), remote)

    def get_timestamp(self, ref):
        return self._data_cache.get_timestamp(ConanReference(ref))

    def set_timestamp(self, ref, timestamp):
        return self._data_cache.update_reference(ConanReference(ref), new_timestamp=timestamp)

    def all_refs(self, only_latest_rrev=False):
        # TODO: cache2.0 we are not validating the reference here because it can be a uuid, check
        #  this part in the future
        #  check that we are returning not only the latest ref but all of them
        return [ConanFileReference.loads(f"{ref['reference']}#{ref['rrev']}", validate=False) for ref in
                self._data_cache.list_references(only_latest_rrev=only_latest_rrev)]

    def exists_rrev(self, ref):
        matching_rrevs = self.get_recipe_revisions(ref)
        return len(matching_rrevs) > 0

    def exists_prev(self, ref):
        matching_prevs = self.get_package_revisions(ref)
        return len(matching_prevs) > 0

    def get_package_revisions(self, ref, only_latest_prev=False):
        return [
            PackageReference.loads(f'{pref["reference"]}#{pref["rrev"]}:{pref["pkgid"]}#{pref["prev"]}',
                                   validate=False) for pref in
            self._data_cache.get_package_revisions(ConanReference(ref), only_latest_prev)]

    def get_package_ids(self, ref: ConanReference) -> List[PackageReference]:
        return [
            PackageReference.loads(f'{pref["reference"]}#{pref["rrev"]}:{pref["pkgid"]}',
                                   validate=False) for pref in
            self._data_cache.get_package_ids(ConanReference(ref))]

    def get_build_id(self, ref):
        return self._data_cache.get_build_id(ConanReference(ref))

    def get_recipe_revisions(self, ref, only_latest_rrev=False):
        return [ConanFileReference.loads(f"{rrev['reference']}#{rrev['rrev']}") for rrev in
                self._data_cache.get_recipe_revisions(ConanReference(ref), only_latest_rrev)]

    def get_latest_rrev(self, ref):
        rrevs = self.get_recipe_revisions(ref, True)
        return rrevs[0] if rrevs else None

    def get_latest_prev(self, ref):
        prevs = self.get_package_revisions(ref, True)
        return prevs[0] if prevs else None

    @property
    def store(self):
        return self._store_folder

    def editable_path(self, ref):
        edited_ref = self.editable_packages.get(ref.copy_clear_rev())
        if edited_ref:
            conanfile_path = edited_ref["path"]
            return conanfile_path

    def installed_as_editable(self, ref):
        edited_ref = self.editable_packages.get(ref.copy_clear_rev())
        return bool(edited_ref)

    @property
    def config_install_file(self):
        return os.path.join(self.cache_folder, "config_install.json")

    @property
    def remotes_path(self):
        return os.path.join(self.cache_folder, REMOTES)

    @property
    def registry(self):
        return RemoteRegistry(self, self._output)

    def _no_locks(self):
        if self._no_lock is None:
            self._no_lock = self.config.cache_no_locks
        return self._no_lock

    @property
    def artifacts_properties_path(self):
        return os.path.join(self.cache_folder, ARTIFACTS_PROPERTIES_FILE)

    def read_artifacts_properties(self):
        ret = {}
        if not os.path.exists(self.artifacts_properties_path):
            save(self.artifacts_properties_path, "")
            return ret
        try:
            contents = load(self.artifacts_properties_path)
            for line in contents.splitlines():
                if line and not line.strip().startswith("#"):
                    tmp = line.split("=", 1)
                    if len(tmp) != 2:
                        raise Exception()
                    name = tmp[0].strip()
                    value = tmp[1].strip()
                    ret[str(name)] = str(value)
            return ret
        except Exception:
            raise ConanException("Invalid %s file!" % self.artifacts_properties_path)

    @property
    def config(self):
        if not self._config:
            self.initialize_config()
            self._config = ConanClientConfigParser(self.conan_conf_path)
        return self._config

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
                self._new_config.loads(load(self.new_config_path))
        return self._new_config

    @property
    def localdb(self):
        localdb_filename = os.path.join(self.cache_folder, LOCALDB)
        encryption_key = os.getenv('CONAN_LOGIN_ENCRYPTION_KEY', None)
        return LocalDB.create(localdb_filename, encryption_key=encryption_key)

    @property
    def conan_conf_path(self):
        return os.path.join(self.cache_folder, CONAN_CONF)

    @property
    def profiles_path(self):
        return os.path.join(self.cache_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return os.path.join(self.cache_folder, CONAN_SETTINGS)

    @property
    def generators_path(self):
        return os.path.join(self.cache_folder, GENERATORS_FOLDER)

    @property
    def default_profile_path(self):
        if os.path.isabs(self.config.default_profile):
            return self.config.default_profile
        else:
            return os.path.join(self.cache_folder, PROFILES_FOLDER, self.config.default_profile)

    @property
    def hooks_path(self):
        """
        :return: Hooks folder in client cache
        """
        return os.path.join(self.cache_folder, HOOKS_FOLDER)

    @property
    def default_profile(self):
        self.initialize_default_profile()
        default_profile, _ = read_profile(self.default_profile_path, os.getcwd(), self.profiles_path)
        return default_profile

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""
        self.initialize_settings()
        content = load(self.settings_path)
        return Settings.loads(content)

    @property
    def hooks(self):
        """Returns a list of hooks inside the hooks folder"""
        hooks = []
        for hook_name in os.listdir(self.hooks_path):
            if os.path.isfile(hook_name) and hook_name.endswith(".py"):
                hooks.append(hook_name[:-3])
        return hooks

    @property
    def generators(self):
        """Returns a list of generator paths inside the generators folder"""
        generators = []
        if os.path.exists(self.generators_path):
            for path in os.listdir(self.generators_path):
                generator = os.path.join(self.generators_path, path)
                if os.path.isfile(generator) and generator.endswith(".py"):
                    generators.append(generator)
        return generators

    def remove_locks(self):
        folders = list_folder_subdirs(self._store_folder, 4)
        for folder in folders:
            conan_folder = os.path.join(self._store_folder, folder)
            Lock.clean(conan_folder)
            shutil.rmtree(os.path.join(conan_folder, "locks"), ignore_errors=True)

    def get_template(self, template_name, user_overrides=False):
        # TODO: It can be initialized only once together with the Conan app
        loaders = [dict_loader]
        if user_overrides:
            loaders.insert(0, FileSystemLoader(os.path.join(self.cache_folder, 'templates')))
        env = Environment(loader=ChoiceLoader(loaders),
                          autoescape=select_autoescape(['html', 'xml']))
        return env.get_template(template_name)

    def initialize_config(self):
        if not os.path.exists(self.conan_conf_path):
            save(self.conan_conf_path, normalize(get_default_client_conf()))

    def reset_config(self):
        if os.path.exists(self.conan_conf_path):
            remove(self.conan_conf_path)
        self.initialize_config()

    def initialize_default_profile(self):
        if not os.path.exists(self.default_profile_path):
            self._output.writeln("Auto detecting your dev setup to initialize the "
                                 "default profile (%s)" % self.default_profile_path,
                                 Color.BRIGHT_YELLOW)

            default_settings = detect_defaults_settings(self._output,
                                                        profile_path=self.default_profile_path)
            self._output.writeln("Default settings", Color.BRIGHT_YELLOW)
            self._output.writeln("\n".join(["\t%s=%s" % (k, v) for (k, v) in default_settings]),
                                 Color.BRIGHT_YELLOW)
            self._output.writeln("*** You can change them in %s ***" % self.default_profile_path,
                                 Color.BRIGHT_MAGENTA)
            self._output.writeln("*** Or override with -s compiler='other' -s ...s***\n\n",
                                 Color.BRIGHT_MAGENTA)

            default_profile = Profile()
            tmp = OrderedDict(default_settings)
            default_profile.update_settings(tmp)
            save(self.default_profile_path, default_profile.dumps())

    def reset_default_profile(self):
        if os.path.exists(self.default_profile_path):
            remove(self.default_profile_path)
        self.initialize_default_profile()

    def initialize_settings(self):
        if not os.path.exists(self.settings_path):
            save(self.settings_path, normalize(get_default_settings_yml()))

    def reset_settings(self):
        if os.path.exists(self.settings_path):
            remove(self.settings_path)
        self.initialize_settings()
