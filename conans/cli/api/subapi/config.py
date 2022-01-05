import json
import os

from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.client.conf.config_installer import configuration_reinstall
from conans.errors import ConanException
from conans.util.files import load, save, remove


class ConfigAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def home(self):
        return self.conan_api.cache_folder

    @api_method
    def install(self, path_or_url, verify_ssl, config_type=None, args=None,
                source_folder=None, target_folder=None):
        # TODO: We probably want to split this into git-folder-http cases?
        from conans.client.conf.config_installer import configuration_install
        app = ConanApp(self.conan_api.cache_folder)
        return configuration_install(app, path_or_url, verify_ssl,
                                     config_type=config_type, args=args,
                                     source_folder=source_folder, target_folder=target_folder)

    @api_method
    def reinstall(self):
        app = ConanApp(self.conan_api.cache_folder)
        configuration_reinstall(app)

    @api_method
    def install_list(self):
        app = ConanApp(self.conan_api.cache_folder)
        if not os.path.isfile(app.cache.config_install_file):
            return []
        return json.loads(load(app.cache.config_install_file))

    @api_method
    def install_remove(self, index):
        app = ConanApp(self.conan_api.cache_folder)
        if not os.path.isfile(app.cache.config_install_file):
            raise ConanException("There is no config data. Need to install config first.")
        configs = json.loads(load(app.cache.config_install_file))
        try:
            configs.pop(index)
        except Exception as e:
            raise ConanException("Config %s can't be removed: %s" % (index, str(e)))
        save(app.cache.config_install_file, json.dumps(configs))

    @api_method
    def init(self, force=False):
        # TODO: revise this API use case and the initialization of Home config
        app = ConanApp(self.conan_api.cache_folder)
        # Only the files that are automatically created by Conan, not default profile
        if force:
            if os.path.exists(app.cache.conan_conf_path):
                remove(app.cache.conan_conf_path)
            if os.path.exists(app.cache.remotes_path):
                remove(app.cache.remotes_path)
            if os.path.exists(app.cache.settings_path):
                remove(app.cache.settings_path)

        app.cache.initialize_settings()
        app.cache.initialize_config()
        app.cache.remotes_registry.initialize_remotes()
