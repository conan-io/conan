import os
from conans.errors import ConanException
import logging
from conans.util.env_reader import get_env
from conans.util.files import save, load
from six.moves.configparser import ConfigParser, NoSectionError
from conans.model.values import Values
import urllib
from conans.paths import conan_expand_user
from collections import OrderedDict

MIN_SERVER_COMPATIBLE_VERSION = '0.12.0'

default_settings_yml = """os: [Windows, Linux, Macos, Android, iOS, FreeBSD, SunOS]
arch: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8]
compiler:
    sun-cc:
       version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
       threads: [None, posix]
       libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "6.3"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""


default_client_conf = '''[storage]
# This is the default path, but you can write your own
path: ~/.conan/data

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
                result = conan_expand_user(self.storage["path"])
        except KeyError:
            result = None
        result = get_env('CONAN_STORAGE_PATH', result)
        return result

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

    def settings_defaults(self, settings):
        default_settings = self.get_conf("settings_defaults")
        values = Values.from_list(default_settings)
        settings.values = values
        mixed_settings = self._mix_settings_with_env(default_settings)
        values = Values.from_list(mixed_settings)
        settings.values = values

    def _mix_settings_with_env(self, settings):
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
        for name, value in settings:
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
        return list(ret.items())
