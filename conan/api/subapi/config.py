from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp


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
    def get(self, name, default=None, check_type=None):
        app = ConanApp(self.conan_api.cache_folder)
        return app.cache.new_config.get(name, default=default, check_type=check_type)
