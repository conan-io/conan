import os
from conans.util.files import save, load
from conans.paths import StorePaths
from conans.model.settings import Settings
from conans.client.conf import ConanClientConfigParser, default_client_conf, default_settings_yml
from conans.model.values import Values
from conans.client.detect import detect_defaults_settings

CONAN_CONF = 'conan.conf'
CONAN_SETTINGS = "settings.yml"
LOCALDB = ".conan.db"
REGISTRY = "registry.txt"


class ConanPaths(StorePaths):
    """ Class to represent/store/compute all the paths involved in the execution
    of conans commands
    """
    def __init__(self, base_folder, store_folder, output):
        self.conan_folder = os.path.join(base_folder, ".conan")
        self._conan_config = None
        self._settings = None
        self._output = output
        self._store_folder = store_folder or self.conan_config.storage_path or self.conan_folder
        StorePaths.__init__(self, self._store_folder)

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
