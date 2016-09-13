import os
from conans.util.files import save, load, relative_dirs, path_exists
from conans.model.settings import Settings
from conans.client.conf import ConanClientConfigParser, default_client_conf, default_settings_yml
from conans.model.values import Values
from conans.client.detect import detect_defaults_settings
from conans.model.ref import ConanFileReference
from os.path import isfile
from conans.model.manifest import FileTreeManifest
from conans.paths import CONAN_MANIFEST, SimplePaths

CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REGISTRY = "registry.txt"


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
    def registry(self):
        return os.path.join(self.conan_folder, REGISTRY)

    @property
    def conan_config(self):
        def generate_default_config_file():
            default_settings = detect_defaults_settings(self._output)
            default_setting_values = Values.from_list(default_settings)
            client_conf = default_client_conf + default_setting_values.dumps()
            save(self.conan_conf_path, client_conf)

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
    def settings_path(self):
        return os.path.join(self.conan_folder, CONAN_SETTINGS)

    @property
    def settings(self):
        """Returns {setting: [value, ...]} defining all the possible
           settings and their values"""
        if not self._settings:
            if not os.path.exists(self.settings_path):
                save(self.settings_path, default_settings_yml)
                settings = Settings.loads(default_settings_yml)
            else:
                content = load(self.settings_path)
                settings = Settings.loads(content)
            settings.values = self.conan_config.settings_defaults
            self._settings = settings
        return self._settings

    def export_paths(self, conan_reference):
        ''' Returns all file paths for a conans (relative to conans directory)'''
        return relative_dirs(self.export(conan_reference))

    def package_paths(self, package_reference):
        ''' Returns all file paths for a package (relative to conans directory)'''
        return relative_dirs(self.package(package_reference))

    def conan_packages(self, conan_reference):
        """ Returns a list of package_id from a conans """
        assert isinstance(conan_reference, ConanFileReference)
        packages_dir = self.packages(conan_reference)
        try:
            packages = [dirname for dirname in os.listdir(packages_dir)
                        if not isfile(os.path.join(packages_dir, dirname))]
        except:  # if there isn't any package folder
            packages = []
        return packages

    def load_digest(self, conan_reference):
        '''conan_id = sha(zip file)'''
        filename = os.path.join(self.export(conan_reference), CONAN_MANIFEST)
        return FileTreeManifest.loads(load(filename))

    def conan_manifests(self, conan_reference):
        digest_path = self.digestfile_conanfile(conan_reference)
        return self._digests(digest_path)

    def package_manifests(self, package_reference):
        digest_path = self.digestfile_package(package_reference)
        return self._digests(digest_path)

    def _digests(self, digest_path):
        if not path_exists(digest_path, self.store):
            return None, None
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
