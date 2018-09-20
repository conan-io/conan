import os
import shutil
from os.path import join, normpath
from collections import OrderedDict

from conans.client.conf import ConanClientConfigParser, default_client_conf, default_settings_yml
from conans.client.conf.detect import detect_defaults_settings
from conans.client.output import Color
from conans.client.profile_loader import read_profile
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.settings import Settings
from conans.paths import SimplePaths, PUT_HEADERS, check_ref_case,\
    CONAN_MANIFEST
from conans.util.files import save, load, normalize, list_folder_subdirs
from conans.util.locks import SimpleLock, ReadLock, WriteLock, NoLock, Lock
from conans.unicode import get_cwd


CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REGISTRY = "registry.txt"
PROFILES_FOLDER = "profiles"
PLUGINS_FOLDER = "plugins"

# Client certificates
CLIENT_CERT = "client.crt"
CLIENT_KEY = "client.key"

# Server authorities file
CACERT_FILE = "cacert.pem"


class ClientCache(SimplePaths):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, base_folder, store_folder, output):
        self.conan_folder = join(base_folder, ".conan")
        self._conan_config = None
        self._settings = None
        self._output = output
        self._store_folder = store_folder or self.conan_config.storage_path or self.conan_folder
        self._default_profile = None
        self._no_lock = None
        self.client_cert_path = normpath(join(self.conan_folder, CLIENT_CERT))
        self.client_cert_key_path = normpath(join(self.conan_folder, CLIENT_KEY))

        super(ClientCache, self).__init__(self._store_folder)

    @property
    def cacert_path(self):
        return normpath(join(self.conan_folder, CACERT_FILE))

    def _no_locks(self):
        if self._no_lock is None:
            self._no_lock = self.conan_config.cache_no_locks
        return self._no_lock

    def conanfile_read_lock(self, conan_ref):
        if self._no_locks():
            return NoLock()
        return ReadLock(self.conan(conan_ref), conan_ref, self._output)

    def conanfile_write_lock(self, conan_ref):
        if self._no_locks():
            return NoLock()
        return WriteLock(self.conan(conan_ref), conan_ref, self._output)

    def conanfile_lock_files(self, conan_ref):
        # Used in ConanRemover
        if self._no_locks():
            return ()
        return WriteLock(self.conan(conan_ref), conan_ref, self._output).files

    def package_lock(self, package_ref):
        if self._no_locks():
            return NoLock()
        return SimpleLock(join(self.conan(package_ref.conan), "locks",
                               package_ref.package_id))

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
    def registry(self):
        return join(self.conan_folder, REGISTRY)

    @property
    def conan_config(self):
        if not self._conan_config:
            if not os.path.exists(self.conan_conf_path):
                save(self.conan_conf_path, normalize(default_client_conf))

            self._conan_config = ConanClientConfigParser(self.conan_conf_path)
        return self._conan_config

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
        if os.path.isabs(self.conan_config.default_profile):
            return self.conan_config.default_profile
        else:
            return join(self.conan_folder, PROFILES_FOLDER,
                        self.conan_config.default_profile)
    @property
    def plugins_path(self):
        """
        :return: Plugins folder in client cache
        """
        return join(self.conan_folder, PLUGINS_FOLDER)

    @property
    def default_profile(self):
        if self._default_profile is None:
            if not os.path.exists(self.default_profile_path):
                self._output.writeln("Auto detecting your dev setup to initialize the "
                                     "default profile (%s)" % self.default_profile_path,
                                     Color.BRIGHT_YELLOW)

                default_settings = detect_defaults_settings(self._output)
                self._output.writeln("Default settings", Color.BRIGHT_YELLOW)
                self._output.writeln("\n".join(["\t%s=%s" % (k, v) for (k, v) in default_settings]),
                                     Color.BRIGHT_YELLOW)
                self._output.writeln("*** You can change them in %s ***" % self.default_profile_path,
                                     Color.BRIGHT_MAGENTA)
                self._output.writeln("*** Or override with -s compiler='other' -s ...s***\n\n",
                                     Color.BRIGHT_MAGENTA)

                self._default_profile = Profile()
                tmp = OrderedDict(default_settings)
                self._default_profile.update_settings(tmp)
                save(self.default_profile_path, self._default_profile.dumps())
            else:
                self._default_profile, _ = read_profile(self.default_profile_path, get_cwd(),
                                                        self.profiles_path)

            # Mix profile settings with environment
            mixed_settings = _mix_settings_with_env(self._default_profile.settings)
            self._default_profile.settings = mixed_settings

        return self._default_profile

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings without values"""
        if not self._settings:
            # TODO: Read default environment settings
            if not os.path.exists(self.settings_path):
                save(self.settings_path, normalize(default_settings_yml))
                settings = Settings.loads(default_settings_yml)
            else:
                content = load(self.settings_path)
                settings = Settings.loads(content)

            self._settings = settings
        return self._settings

    @property
    def plugins(self):
        """Returns a list of plugins inside the plugins folder"""
        plugins = []
        for plugin_name in os.listdir(self.plugins_path):
            if os.path.isfile(plugin_name) and plugin_name.endswith(".py"):
                plugins.append(plugin_name[:-3])
        return plugins

    def conan_packages(self, conan_reference):
        """ Returns a list of package_id from a local cache package folder """
        assert isinstance(conan_reference, ConanFileReference)
        packages_dir = self.packages(conan_reference)
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if os.path.isdir(join(packages_dir, dirname))]
        except OSError:  # if there isn't any package folder
            packages = []
        return packages

    def conan_builds(self, conan_reference):
        """ Returns a list of package ids from a local cache build folder """
        assert isinstance(conan_reference, ConanFileReference)
        builds_dir = self.builds(conan_reference)
        try:
            builds = [dirname for dirname in os.listdir(builds_dir)
                      if os.path.isdir(join(builds_dir, dirname))]
        except OSError:  # if there isn't any package folder
            builds = []
        return builds

    def load_manifest(self, conan_reference):
        """conan_id = sha(zip file)"""
        assert isinstance(conan_reference, ConanFileReference)
        export_folder = self.export(conan_reference)
        check_ref_case(conan_reference, export_folder, self.store)
        return FileTreeManifest.load(export_folder)

    def load_package_manifest(self, package_reference):
        """conan_id = sha(zip file)"""
        package_folder = self.package(package_reference, short_paths=None)
        return FileTreeManifest.load(package_folder)

    def package_manifests(self, package_reference):
        package_folder = self.package(package_reference, short_paths=None)
        if not os.path.exists(os.path.join(package_folder, CONAN_MANIFEST)):
            return None, None
        return self._digests(package_folder)

    @staticmethod
    def _digests(folder, exports_sources_folder=None):
        readed_digest = FileTreeManifest.load(folder)
        expected_digest = FileTreeManifest.create(folder, exports_sources_folder)
        return readed_digest, expected_digest

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

    def remove_locks(self):
        folders = list_folder_subdirs(self._store_folder, 4)
        for folder in folders:
            conan_folder = os.path.join(self._store_folder, folder)
            Lock.clean(conan_folder)
            shutil.rmtree(os.path.join(conan_folder, "locks"), ignore_errors=True)

    def remove_package_locks(self, reference):
        conan_folder = self.conan(reference)
        Lock.clean(conan_folder)
        shutil.rmtree(os.path.join(conan_folder, "locks"), ignore_errors=True)

    def invalidate(self):
        self._conan_config = None
        self._settings = None
        self._default_profile = None
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
