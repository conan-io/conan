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
from conans.model.env_info import unquote

MIN_SERVER_COMPATIBLE_VERSION = '0.12.0'

default_settings_yml = """
os:
    Windows:
    Linux:
    Macos:
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3"]
    FreeBSD:
    SunOS:
arch: [x86, x86_64, ppc64le, ppc64, armv6, armv7, armv7hf, armv8, sparc, sparcv9, mips, mips64]
compiler:
    sun-cc:
       version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
       threads: [None, posix]
       libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9", "5.1", "5.2", "5.3", "5.4", "6.1", "6.2", "6.3"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15"]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release]
"""

# Keep for the migration (could be removed in ~0.22 and directly appended to default_client_conf)
new_default_confs_from_env = '''
[log]
run_to_output = True        # environment CONAN_LOG_RUN_TO_OUTPUT
run_to_file = False         # environment CONAN_LOG_RUN_TO_FILE
level = 50                  # environment CONAN_LOGGING_LEVEL
# trace_file =              # environment CONAN_TRACE_FILE
print_run_commands = False  # environment CONAN_PRINT_RUN_COMMANDS

[general]
compression_level = 9                 # environment CONAN_COMPRESSION_LEVEL
sysrequires_sudo = True               # environment CONAN_SYSREQUIRES_SUDO
# bash_path = ""                      # environment CONAN_BASH_PATH (only windows)
# recipe_linter = False               # environment CONAN_RECIPE_LINTER

# cmake_generator                     # environment CONAN_CMAKE_GENERATOR
# http://www.vtk.org/Wiki/CMake_Cross_Compiling
# cmake_system_name                   # environment CONAN_CMAKE_SYSTEM_NAME
# cmake_system_version                # environment CONAN_CMAKE_SYSTEM_VERSION
# cmake_system_processor              # environment CONAN_CMAKE_SYSTEM_PROCESSOR
# cmake_find_root_path                # environment CONAN_CMAKE_FIND_ROOT_PATH
# cmake_find_root_path_mode_program   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM
# cmake_find_root_path_mode_library   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY
# cmake_find_root_path_mode_include   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE

# cpu_count = 1             # environment CONAN_CPU_COUNT
'''

default_client_conf = '''[storage]
# This is the default path, but you can write your own
path = ~/.conan/data

[proxies]
# Empty section will try to use system proxies.
# If don't want proxy at all, remove section [proxies]
# As documented in http://docs.python-requests.org/en/latest/user/advanced/#proxies
# http = http://user:pass@10.10.1.10:3128/
# http = http://10.10.1.10:3128
# https = http://10.10.1.10:1080

%s

[settings_defaults]

''' % new_default_confs_from_env


class ConanClientConfigParser(ConfigParser, object):

    def __init__(self, filename):
        ConfigParser.__init__(self)
        self.read(filename)
        self.filename = filename

    # So keys are not converted to lowercase, we override the default optionxform
    optionxform = str

    @property
    def env_vars(self):
        ret = {"CONAN_LOG_RUN_TO_OUTPUT": self._env_c("log.run_to_output", "CONAN_LOG_RUN_TO_OUTPUT", "True"),
               "CONAN_LOG_RUN_TO_FILE": self._env_c("log.run_to_file", "CONAN_LOG_RUN_TO_FILE", "False"),
               "CONAN_LOGGING_LEVEL": self._env_c("log.level", "CONAN_LOGGING_LEVEL", "50"),
               "CONAN_TRACE_FILE": self._env_c("log.trace_file", "CONAN_TRACE_FILE", None),
               "CONAN_PRINT_RUN_COMMANDS": self._env_c("log.print_run_commands", "CONAN_PRINT_RUN_COMMANDS", "False"),
               "CONAN_COMPRESSION_LEVEL": self._env_c("general.compression_level", "CONAN_COMPRESSION_LEVEL", "9"),
               "CONAN_PYLINTRC": self._env_c("general.pylintrc", "CONAN_PYLINTRC", None),
               "CONAN_SYSREQUIRES_SUDO": self._env_c("general.sysrequires_sudo", "CONAN_SYSREQUIRES_SUDO", "False"),
               "CONAN_RECIPE_LINTER": self._env_c("general.recipe_linter", "CONAN_RECIPE_LINTER", "True"),
               "CONAN_CPU_COUNT": self._env_c("general.cpu_count", "CONAN_CPU_COUNT", None),
               # http://www.vtk.org/Wiki/CMake_Cross_Compiling
               "CONAN_CMAKE_GENERATOR": self._env_c("general.cmake_generator", "CONAN_CMAKE_GENERATOR", None),
               "CONAN_CMAKE_SYSTEM_NAME": self._env_c("general.cmake_system_name", "CONAN_CMAKE_SYSTEM_NAME", None),
               "CONAN_CMAKE_SYSTEM_VERSION": self._env_c("general.cmake_system_version", "CONAN_CMAKE_SYSTEM_VERSION", None),
               "CONAN_CMAKE_SYSTEM_PROCESSOR": self._env_c("general.cmake_system_processor",
                                                           "CONAN_CMAKE_SYSTEM_PROCESSOR",
                                                           None),
               "CONAN_CMAKE_FIND_ROOT_PATH": self._env_c("general.cmake_find_root_path",
                                                         "CONAN_CMAKE_FIND_ROOT_PATH",
                                                         None),
               "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM": self._env_c("general.cmake_find_root_path_mode_program",
                                                                      "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM",
                                                                      None),
               "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY": self._env_c("general.cmake_find_root_path_mode_library",
                                                                      "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY",
                                                                      None),
               "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE": self._env_c("general.cmake_find_root_path_mode_include",
                                                                      "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE",
                                                                      None),

               "CONAN_BASH_PATH": self._env_c("general.bash_path", "CONAN_BASH_PATH", None),

               }
        # Filter None values
        return {name: value for name, value in ret.items() if value is not None}

    def _env_c(self, var_name, env_var_name, default_value):
        env = os.environ.get(env_var_name, None)
        if env is not None:
            return env
        try:
            return unquote(self.get_item(var_name))
        except ConanException:
            return default_value

    def get_item(self, item):
        if not item:
            return load(self.filename)

        tokens = item.split(".", 1)
        section_name = tokens[0]
        try:
            section = self.items(section_name)
        except NoSectionError:
            raise ConanException("'%s' is not a section of conan.conf" % section_name)
        if len(tokens) == 1:
            result = []
            for item in section:
                result.append(" = ".join(item))
            return "\n".join(result)
        else:
            key = tokens[1]
            try:
                value = dict(section)[key]
                if " #" in value:  # Comments
                    value = value[:value.find(" #")].strip()
            except KeyError:
                raise ConanException("'%s' doesn't exist in [%s]" % (key, section_name))
            return value

    def set_item(self, key, value):
        tokens = key.split(".", 1)
        section_name = tokens[0]
        if not self.has_section(section_name):
            self.add_section(section_name)

        if len(tokens) == 1:  # defining full section
            raise ConanException("You can't set a full section, please specify a key=value")

        key = tokens[1]
        super(ConanClientConfigParser, self).set(section_name, key, value)

        with open(self.filename, "w") as f:
            self.write(f)

    def rm_item(self, item):
        tokens = item.split(".", 1)
        section_name = tokens[0]
        if not self.has_section(section_name):
            raise ConanException("'%s' is not a section of conan.conf" % section_name)

        if len(tokens) == 1:
            self.remove_section(tokens[0])
        else:
            key = tokens[1]
            if not self.has_option(section_name, key):
                raise ConanException("'%s' doesn't exist in [%s]" % (key, section_name))
            self.remove_option(section_name, key)

        with open(self.filename, "w") as f:
            self.write(f)

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
        mixed_settings = _mix_settings_with_env(default_settings)
        values = Values.from_list(mixed_settings)
        settings.values = values


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
