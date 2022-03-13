import os
import platform
import shutil
from collections import OrderedDict

from jinja2 import Environment, select_autoescape, FileSystemLoader, ChoiceLoader, Template

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
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import ARTIFACTS_PROPERTIES_FILE
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.paths.package_layouts.package_editable_layout import PackageEditableLayout
from conans.util.files import list_folder_subdirs, load, normalize, save, remove
from conans.util.locks import Lock

CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REMOTES = "remotes.json"
PROFILES_FOLDER = "profiles"
HOOKS_FOLDER = "hooks"
TEMPLATES_FOLDER = "templates"
GENERATORS_FOLDER = "generators"


def _is_case_insensitive_os():
    system = platform.system()
    return system != "Linux" and system != "FreeBSD" and system != "SunOS"


if _is_case_insensitive_os():
    def _check_ref_case(ref, store_folder):
        if not os.path.exists(store_folder):
            return

        tmp = store_folder
        for part in ref.dir_repr().split("/"):
            items = os.listdir(tmp)
            try:
                idx = [item.lower() for item in items].index(part.lower())
                if part != items[idx]:
                    raise ConanException("Requested '{requested}', but found case incompatible"
                                         " recipe with name '{existing}' in the cache. Case"
                                         " insensitive filesystem can't manage this.\n Remove"
                                         " existing recipe '{existing}' and try again.".format(
                        requested=str(ref), existing=items[idx]
                    ))
                tmp = os.path.normpath(tmp + os.sep + part)
            except ValueError:
                return
else:
    def _check_ref_case(ref, store_folder):  # @UnusedVariable
        pass


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
        # Just call it to make it raise in case of short_paths misconfiguration
        _ = self.config.short_paths_home

    def all_refs(self):
        subdirs = list_folder_subdirs(basedir=self._store_folder, level=4)
        return [ConanFileReference.load_dir_repr(folder) for folder in subdirs]

    @property
    def store(self):
        return self._store_folder

    def installed_as_editable(self, ref):
        return isinstance(self.package_layout(ref), PackageEditableLayout)

    @property
    def config_install_file(self):
        return os.path.join(self.cache_folder, "config_install.json")

    def package_layout(self, ref, short_paths=None):
        assert isinstance(ref, ConanFileReference), "It is a {}".format(type(ref))
        edited_ref = self.editable_packages.get(ref.copy_clear_rev())
        if edited_ref:
            conanfile_path = edited_ref["path"]
            layout_file = edited_ref["layout"]
            return PackageEditableLayout(os.path.dirname(conanfile_path), layout_file, ref,
                                         conanfile_path, edited_ref.get("output_folder"))
        else:
            _check_ref_case(ref, self.store)
            base_folder = os.path.normpath(os.path.join(self.store, ref.dir_repr()))
            return PackageCacheLayout(base_folder=base_folder, ref=ref,
                                      short_paths=short_paths, no_lock=self._no_locks())

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
                text = load(self.new_config_path)
                content = Template(text).render({"platform": platform, "os": os})
                self._new_config.loads(content)
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

        # Mix profile settings with environment
        mixed_settings = _mix_settings_with_env(default_profile.settings)
        default_profile.settings = mixed_settings
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

    def delete_empty_dirs(self, deleted_refs):
        """ Method called by ConanRemover.remove() to clean up from the cache empty folders
        :param deleted_refs: The recipe references that the remove() has been removed
        """
        for ref in deleted_refs:
            ref_path = self.package_layout(ref).base_folder()
            for _ in range(4):
                if os.path.exists(ref_path):
                    try:  # Take advantage that os.rmdir does not delete non-empty dirs
                        os.rmdir(ref_path)
                    except OSError:
                        break  # not empty
                ref_path = os.path.dirname(ref_path)

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


def _mix_settings_with_env(settings):
    """Reads CONAN_ENV_XXXX variables from environment
    and if it's defined uses these value instead of the default
    from conf file. If you specify a compiler with ENV variable you
    need to specify all the subsettings, the file defaulted will be
    ignored"""

    # FIXME: Conan 2.0. This should be removed, it only applies to default profile, not others

    def get_env_value(name_):
        env_name = "CONAN_ENV_%s" % name_.upper().replace(".", "_")
        return os.getenv(env_name, None)

    def get_setting_name(env_name):
        return env_name[10:].lower().replace("_", ".")

    ret = OrderedDict()
    for name, value in settings.items():
        if get_env_value(name):
            ret[name] = get_env_value(name)
        else:
            # being a subsetting, if parent exist in env discard this, because
            # env doesn't define this setting. EX: env=>Visual Studio but
            # env doesn't define compiler.libcxx
            if "." not in name or not get_env_value(name.split(".")[0]):
                ret[name] = value
    # Now read if there are more env variables
    for env, value in sorted(os.environ.items()):
        if env.startswith("CONAN_ENV_") and get_setting_name(env) not in ret:
            ret[get_setting_name(env)] = value
    return ret
