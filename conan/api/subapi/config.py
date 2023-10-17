import os
import platform
import textwrap

from jinja2 import Environment, FileSystemLoader

from conan import conan_version
from conan.internal.api import detect_api
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conans.model.conf import ConfDefinition
from conans.util.files import load, save


class ConfigAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api
        self._new_config = None

    def home(self):
        return self.conan_api.cache_folder

    def install(self, path_or_url, verify_ssl, config_type=None, args=None,
                source_folder=None, target_folder=None):
        # TODO: We probably want to split this into git-folder-http cases?
        from conans.client.conf.config_installer import configuration_install
        app = ConanApp(self.conan_api.cache_folder)
        return configuration_install(app, path_or_url, verify_ssl,
                                     config_type=config_type, args=args,
                                     source_folder=source_folder, target_folder=target_folder)

    def get(self, name, default=None, check_type=None):
        return self.global_conf.get(name, default=default, check_type=check_type)

    def show(self, pattern):
        return self.global_conf.show(pattern)

    @property
    def global_conf(self):
        """ this is the new global.conf to replace the old conan.conf that contains
        configuration defined with the new syntax as in profiles, this config will be composed
        to the profile ones and passed to the conanfiles.conf, which can be passed to collaborators
        """
        if self._new_config is None:
            self._new_config = ConfDefinition()
            cache_folder = self.conan_api.cache_folder
            home_paths = HomePaths(cache_folder)
            global_conf_path = home_paths.global_conf_path
            if os.path.exists(global_conf_path):
                text = load(global_conf_path)
                distro = None
                if platform.system() in ["Linux", "FreeBSD"]:
                    import distro
                template = Environment(loader=FileSystemLoader(cache_folder)).from_string(text)
                content = template.render({"platform": platform, "os": os, "distro": distro,
                                           "conan_version": conan_version,
                                           "conan_home_folder": cache_folder,
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
                save(global_conf_path, default_global_conf)
        return self._new_config
