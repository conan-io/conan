import os

from conans.errors import ConanException
from conans.util.files import save, load, normalize
from conans.model.settings import Settings
from conans.client.conf import ConanClientConfigParser, default_client_conf, default_settings_yml
from conans.model.values import Values
from conans.client.detect import detect_defaults_settings
from conans.model.ref import ConanFileReference
from conans.model.manifest import FileTreeManifest
from conans.paths import SimplePaths, CONANINFO, PUT_HEADERS
from genericpath import isdir
from conans.model.info import ConanInfo


CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REGISTRY = "registry.txt"
PROFILES_FOLDER = "profiles"


class ClientCache(SimplePaths):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands. Accesses to real disk and reads/write things. (OLD client ConanPaths)
    """

    def __init__(self, base_folder, store_folder, output):
        self.conan_folder = os.path.join(base_folder, ".conan")
        self._conan_config = None
        self._settings = None
        self._output = output
        self._store_folder = store_folder or self.conan_config.storage_path or self.conan_folder
        super(ClientCache, self).__init__(self._store_folder)

    @property
    def put_headers_path(self):
        return os.path.join(self.conan_folder, PUT_HEADERS)

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
        return os.path.join(self.conan_folder, REGISTRY)

    @property
    def conan_config(self):
        def generate_default_config_file():
            default_settings = detect_defaults_settings(self._output)
            default_setting_values = Values.from_list(default_settings)
            client_conf = default_client_conf + default_setting_values.dumps()
            save(self.conan_conf_path, normalize(client_conf))

        if not self._conan_config:
            if not os.path.exists(self.conan_conf_path):
                generate_default_config_file()

            self._conan_config = ConanClientConfigParser(self.conan_conf_path)

        return self._conan_config

    @property
    def localdb(self):
        return os.path.join(self.conan_folder, LOCALDB)

    @property
    def conan_conf_path(self):
        return os.path.join(self.conan_folder, CONAN_CONF)

    @property
    def profiles_path(self):
        return os.path.join(self.conan_folder, PROFILES_FOLDER)

    @property
    def settings_path(self):
        return os.path.join(self.conan_folder, CONAN_SETTINGS)

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings and their values"""
        if not self._settings:
            # TODO: Read default environment settings
            if not os.path.exists(self.settings_path):
                save(self.settings_path, normalize(default_settings_yml))
                settings = Settings.loads(default_settings_yml)
            else:
                content = load(self.settings_path)
                settings = Settings.loads(content)
            self.conan_config.settings_defaults(settings)
            self._settings = settings
        return self._settings

    def conan_packages(self, conan_reference):
        """ Returns a list of package_id from a local cache package folder """
        assert isinstance(conan_reference, ConanFileReference)
        packages_dir = self.packages(conan_reference)
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if isdir(os.path.join(packages_dir, dirname))]
        except:  # if there isn't any package folder
            packages = []
        return packages

    def conan_builds(self, conan_reference):
        """ Returns a list of package ids from a local cache build folder """
        assert isinstance(conan_reference, ConanFileReference)
        builds_dir = self.builds(conan_reference)
        try:
            builds = [dirname for dirname in os.listdir(builds_dir)
                      if isdir(os.path.join(builds_dir, dirname))]
        except:  # if there isn't any package folder
            builds = []
        return builds

    def load_manifest(self, conan_reference):
        '''conan_id = sha(zip file)'''
        filename = self.digestfile_conanfile(conan_reference)
        return FileTreeManifest.loads(load(filename))

    def load_package_manifest(self, package_reference):
        '''conan_id = sha(zip file)'''
        filename = self.digestfile_package(package_reference, short_paths=None)
        return FileTreeManifest.loads(load(filename))

    def read_package_recipe_hash(self, package_folder):
        filename = os.path.join(package_folder, CONANINFO)
        info = ConanInfo.loads(load(filename))
        return info.recipe_hash

    def conan_manifests(self, conan_reference):
        digest_path = self.digestfile_conanfile(conan_reference)
        if not os.path.exists(digest_path):
            return None, None
        return self._digests(digest_path)

    def package_manifests(self, package_reference):
        digest_path = self.digestfile_package(package_reference, short_paths=None)
        if not os.path.exists(digest_path):
            return None, None
        return self._digests(digest_path)

    def _digests(self, digest_path):
        readed_digest = FileTreeManifest.loads(load(digest_path))
        expected_digest = FileTreeManifest.create(os.path.dirname(digest_path))
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
