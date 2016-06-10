import os
from conans.errors import ConanException
import logging
from conans.util.env_reader import get_env
from conans.util.files import save, load
from six.moves.configparser import ConfigParser, NoSectionError
from conans.model.values import Values
import urllib

MIN_SERVER_COMPATIBLE_VERSION = '0.6.0'

cur_dir = os.path.dirname(os.path.abspath(__file__))
default_settings_yml_file = open(os.path.join(cur_dir, "settings.yml"))
default_settings_yml = default_settings_yml_file.read()
default_client_conf_file = open(os.path.join(cur_dir, "client.conf"))
default_client_conf = default_client_conf_file.read()

class ConanClientConfigParser(ConfigParser):

    def __init__(self, filename):
        ConfigParser.__init__(self)
        self.read(filename)

    def get_conf(self, varname):
        """Gets the section from config file or raises an exception"""
        try:
            return self.items(varname)
        except NoSectionError:
            raise ConanException("Invalid configuration, missing %s" % varname)

    @property
    def storage(self):
        return dict(self.get_conf("storage"))

    @property
    def storage_path(self):
        try:
            conan_user_home = os.getenv("CONAN_USER_HOME")
            if conan_user_home:
                storage = self.storage["path"]
                if storage[:2] == "~/":
                    storage = storage[2:]
                result = os.path.join(conan_user_home, storage)
            else:
                result = os.path.expanduser(self.storage["path"])
        except KeyError:
            result = None
        result = get_env('CONAN_STORAGE_PATH', result)
        return result

    @property
    def deprecated_remotes(self):
        return self.get_conf("remotes")

    @property
    def proxies(self):
        """ optional field, might not exist
        """
        try:
            proxies = self.get_conf("proxies")
            # If there is proxies section, but empty, it will try to use system proxy
            if not proxies:
                return urllib.getproxies()
            return dict(proxies)
        except:
            return None

    @property
    def settings_defaults(self):
        default_settings = self.get_conf("settings_defaults")
        values = Values.from_list(default_settings)
        return values
