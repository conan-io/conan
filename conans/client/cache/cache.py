import os
import shutil
from collections import OrderedDict
from os.path import join, normpath

from conans.client.cache.editable import EditablePackages
from conans.client.cache.remote_registry import default_remotes, dump_registry, \
    migrate_registry_file, RemoteRegistry
from conans.client.conf import ConanClientConfigParser, default_client_conf, default_settings_yml
from conans.client.conf.detect import detect_defaults_settings
from conans.client.output import Color
from conans.client.profile_loader import read_profile
from conans.errors import ConanException
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import PUT_HEADERS, SYSTEM_REQS_FOLDER
from conans.paths.package_layouts.package_cache_layout import PackageCacheLayout
from conans.paths.package_layouts.package_editable_layout import PackageEditableLayout
from conans.paths.simple_paths import SimplePaths
from conans.paths.simple_paths import check_ref_case
from conans.unicode import get_cwd
from conans.util.files import list_folder_subdirs, load, normalize, save, rmdir
from conans.util.locks import Lock

CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REGISTRY = "registry.txt"
REGISTRY_JSON = "registry.json"
PROFILES_FOLDER = "profiles"
HOOKS_FOLDER = "hooks"


# Client certificates
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"


class ClientCache(SimplePaths):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, base_folder, store_folder, output):
        self.conan_folder = join(base_folder, ".conan")
        self._config = None
        self._output = output
        self._store_folder = store_folder or self.config.storage_path or self.conan_folder
        self._no_lock = None
        self.client_cert_path = normpath(join(self.conan_folder, CLIENT_CERT))
        self.client_cert_key_path = normpath(join(self.conan_folder, CLIENT_KEY))
        self._registry = None

        super(ClientCache, self).__init__(self._store_folder)
        self.editable_packages = EditablePackages(self.conan_folder)

    @property
    def config_install_file(self):
        return os.path.join(self.conan_folder, "config_install.json")

    def package_layout(self, ref, short_paths=None, *args, **kwargs):
        assert isinstance(ref, ConanFileReference), "It is a {}".format(type(ref))
        edited_ref = self.editable_packages.get(ref.copy_clear_rev())
        if edited_ref:
            base_path = edited_ref["path"]
            layout_file = edited_ref["layout"]
            return PackageEditableLayout(base_path, layout_file, ref)
        else:
            check_ref_case(ref, self.store)
            base_folder = os.path.normpath(os.path.join(self.store, ref.dir_repr()))
            return PackageCacheLayout(base_folder=base_folder, ref=ref,
                                      short_paths=short_paths, no_lock=self._no_locks())

    @property
    def registry(self):
        if not self._registry:
            self._registry = RemoteRegistry(self.registry_path, self._output)
        return self._registry

    @property
    def cacert_path(self):
        return self.config.cacert_path

    def _no_locks(self):
        if self._no_lock is None:
            self._no_lock = self.config.cache_no_locks
        return self._no_lock

    def conanfile_read_lock(self, ref):
        layout = self.package_layout(ref)
        return layout.conanfile_read_lock(self._output)

    def conanfile_write_lock(self, ref):
        layout = self.package_layout(ref)
        return layout.conanfile_write_lock(self._output)

    def conanfile_lock_files(self, ref):
        layout = self.package_layout(ref)
        return layout.conanfile_lock_files(self._output)

    def package_lock(self, pref):
        layout = self.package_layout(pref.ref)
        return layout.package_lock(pref)

    @property
    def put_headers_path(self):
        return join(self.conan_folder, PUT_HEADERS)

    def read_put_headers(self):
        ret = {}
        if not os.path.exists(self.put_headers_path):
            save(self.put_headers_path, "")
            return ret
        try:
            contents = load(self.put_headers_path)
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
            raise ConanException("Invalid %s file!" % self.put_headers_path)

    @property
    def registry_path(self):
        reg_json_path = join(self.conan_folder, REGISTRY_JSON)
        if not os.path.exists(reg_json_path):
            # Load the txt if exists and convert to json
            reg_txt = join(self.conan_folder, REGISTRY)
            if os.path.exists(reg_txt):
                migrate_registry_file(reg_txt, reg_json_path)
            else:
                self._output.warn("Remotes registry file missing, "
                                  "creating default one in %s" % reg_json_path)
                save(reg_json_path, dump_registry(default_remotes, {}, {}))
        return reg_json_path

    @property
    def config(self):
        if not self._config:
            if not os.path.exists(self.conan_conf_path):
                save(self.conan_conf_path, normalize(default_client_conf))

            self._config = ConanClientConfigParser(self.conan_conf_path)
        return self._config

    @property
    def localdb(self):
        return join(self.conan_folder, LOCALDB)

    @property
    def conan_conf_path(self):
        return join(self.conan_folder, CONAN_CONF)

    @property
    def profiles_path(self):
        return join(self.conan_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return join(self.conan_folder, CONAN_SETTINGS)

    @property
    def default_profile_path(self):
        if os.path.isabs(self.config.default_profile):
            return self.config.default_profile
        else:
            return join(self.conan_folder, PROFILES_FOLDER,
                        self.config.default_profile)

    @property
    def hooks_path(self):
        """
        :return: Hooks folder in client cache
        """
        return join(self.conan_folder, HOOKS_FOLDER)

    @property
    def default_profile(self):
        if not os.path.exists(self.default_profile_path):
            self._output.writeln("Auto detecting your dev setup to initialize the "
                                 "default profile (%s)" % self.default_profile_path,
                                 Color.BRIGHT_YELLOW)

            default_settings = detect_defaults_settings(self._output, profile_path=self.default_profile_path)
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
        else:
            default_profile, _ = read_profile(self.default_profile_path, get_cwd(),
                                              self.profiles_path)

        # Mix profile settings with environment
        mixed_settings = _mix_settings_with_env(default_profile.settings)
        default_profile.settings = mixed_settings
        return default_profile

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""

        if not os.path.exists(self.settings_path):
            save(self.settings_path, normalize(default_settings_yml))
            settings = Settings.loads(default_settings_yml)
        else:
            content = load(self.settings_path)
            settings = Settings.loads(content)

        return settings

    @property
    def hooks(self):
        """Returns a list of hooks inside the hooks folder"""
        hooks = []
        for hook_name in os.listdir(self.hooks_path):
            if os.path.isfile(hook_name) and hook_name.endswith(".py"):
                hooks.append(hook_name[:-3])
        return hooks

    def conan_packages(self, ref):
        """ Returns a list of package_id from a local cache package folder """
        layout = self.package_layout(ref)
        return layout.conan_packages()

    def conan_builds(self, ref):
        """ Returns a list of package ids from a local cache build folder """
        layout = self.package_layout(ref)
        return layout.conan_builds()

    def delete_empty_dirs(self, deleted_refs):
        for ref in deleted_refs:
            ref_path = self.conan(ref)
            for _ in range(4):
                if os.path.exists(ref_path):
                    try:  # Take advantage that os.rmdir does not delete non-empty dirs
                        os.rmdir(ref_path)
                    except OSError:
                        break  # not empty
                ref_path = os.path.dirname(ref_path)

    def remove_package_system_reqs(self, reference):
        assert isinstance(reference, ConanFileReference)
        conan_folder = self.conan(reference)
        system_reqs_folder = os.path.join(conan_folder, SYSTEM_REQS_FOLDER)
        if not os.path.exists(conan_folder):
            raise ValueError("%s does not exist" % repr(reference))
        if not os.path.exists(system_reqs_folder):
            return
        try:
            rmdir(system_reqs_folder)
        except Exception as e:
            raise ConanException("Unable to remove system requirements at %s: %s" % (system_reqs_folder, str(e)))

    def remove_locks(self):
        folders = list_folder_subdirs(self._store_folder, 4)
        for folder in folders:
            conan_folder = os.path.join(self._store_folder, folder)
            Lock.clean(conan_folder)
            shutil.rmtree(os.path.join(conan_folder, "locks"), ignore_errors=True)

    def remove_package_locks(self, ref):
        package_layout = self.package_layout(ref=ref)
        package_layout.remove_package_locks()

    def invalidate(self):
        self._config = None
        self._no_lock = None


def _mix_settings_with_env(settings):
    """Reads CONAN_ENV_XXXX variables from environment
    and if it's defined uses these value instead of the default
    from conf file. If you specify a compiler with ENV variable you
    need to specify all the subsettings, the file defaulted will be
    ignored"""

    def get_env_value(name):
        env_name = "CONAN_ENV_%s" % name.upper().replace(".", "_")
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
