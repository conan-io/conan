import os
from conans.errors import ConanException
import logging
from conans.util.env_reader import get_env
from conans.util.files import save, load
from six.moves.configparser import ConfigParser, NoSectionError
from conans.model.values import Values
import urllib

MIN_SERVER_COMPATIBLE_VERSION = '0.6.0'

default_settings_yml = """
os: [Windows, Linux, Macos, Android, iOS]
arch: [x86, x86_64, armv6, armv7, armv7hf, armv8]
compiler:
    gcc:
        version: ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3"]
        libcxx: [libstdc++, libstdc++11]
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""


default_client_conf = '''
[storage]
# This is the default path, but you can write your own
path: ~/.conan/data

[remotes]
conan.io: https://server.conan.io
local: http://localhost:9300

[proxies]
# Empty section will try to use system proxies.
# If don't want proxy at all, remove section [proxies]
# As documented in http://docs.python-requests.org/en/latest/user/advanced/#proxies
# http: http://user:pass@10.10.1.10:3128/
# http: http://10.10.1.10:3128
# https: http://10.10.1.10:1080

[settings_defaults]

'''


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
