import os

from six.moves import urllib
from six.moves.configparser import ConfigParser, NoSectionError

from conans.errors import ConanException
from conans.model.env_info import unquote
from conans.paths import DEFAULT_PROFILE_NAME, conan_expand_user, CACERT_FILE
from conans.util.env_reader import get_env
from conans.util.files import load


default_settings_yml = """
# Only for cross building, 'os_build/arch_build' is the system that runs Conan
os_build: [Windows, WindowsStore, Linux, Macos, FreeBSD, SunOS]
arch_build: [x86, x86_64, ppc32, ppc64le, ppc64, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x]

# Only for building cross compilation tools, 'os_target/arch_target' is the system for
# which the tools generate code
os_target: [Windows, Linux, Macos, Android, iOS, watchOS, tvOS, FreeBSD, SunOS, Arduino]
arch_target: [x86, x86_64, ppc32, ppc64le, ppc64, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x]

# Rest of the settings are "host" settings:
# - For native building/cross building: Where the library/program will run.
# - For building cross compilation tools: Where the cross compiler will run.
os:
    Windows:
        subsystem: [None, cygwin, msys, msys2, wsl]
    WindowsStore:
        version: ["8.1", "10.0"]
    Linux:
    Macos:
        version: [None, "10.6", "10.7", "10.8", "10.9", "10.10", "10.11", "10.12", "10.13", "10.14"]
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3", "11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1"]
    watchOS:
        version: ["4.0", "4.1", "4.2", "4.3", "5.0", "5.1"]
    tvOS:
        version: ["11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1"]
    FreeBSD:
    SunOS:
    Arduino:
        board: ANY
arch: [x86, x86_64, ppc32, ppc64le, ppc64, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
        threads: [None, posix]
        libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc:
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                  "5", "5.1", "5.2", "5.3", "5.4", "5.5",
                  "6", "6.1", "6.2", "6.3", "6.4",
                  "7", "7.1", "7.2", "7.3",
                  "8", "8.1", "8.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
    Visual Studio:
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15", "16"]
        toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp,
                  v140, v140_xp, v140_clang_c2, LLVM-vs2012, LLVM-vs2012_xp,
                  LLVM-vs2013, LLVM-vs2013_xp, LLVM-vs2014, LLVM-vs2014_xp,
                  LLVM-vs2017, LLVM-vs2017_xp, v141, v141_xp, v141_clang_c2, v142]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0",
                  "5.0", "6.0", "7.0",
                  "8"]
        libcxx: [libstdc++, libstdc++11, libc++]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0", "9.1", "10.0"]
        libcxx: [libstdc++, libc++]

build_type: [None, Debug, Release, RelWithDebInfo, MinSizeRel]
cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
"""

default_client_conf = """
[log]
run_to_output = True        # environment CONAN_LOG_RUN_TO_OUTPUT
run_to_file = False         # environment CONAN_LOG_RUN_TO_FILE
level = 50                  # environment CONAN_LOGGING_LEVEL
# trace_file =              # environment CONAN_TRACE_FILE
print_run_commands = False  # environment CONAN_PRINT_RUN_COMMANDS

[general]
default_profile = %s
compression_level = 9                 # environment CONAN_COMPRESSION_LEVEL
sysrequires_sudo = True               # environment CONAN_SYSREQUIRES_SUDO
request_timeout = 60                  # environment CONAN_REQUEST_TIMEOUT (seconds)
# sysrequires_mode = enabled          # environment CONAN_SYSREQUIRES_MODE (allowed modes enabled/verify/disabled)
# vs_installation_preference = Enterprise, Professional, Community, BuildTools # environment CONAN_VS_INSTALLATION_PREFERENCE
# verbose_traceback = False           # environment CONAN_VERBOSE_TRACEBACK
# error_on_override = False           # environment CONAN_ERROR_ON_OVERRIDE
# bash_path = ""                      # environment CONAN_BASH_PATH (only windows)
# recipe_linter = False               # environment CONAN_RECIPE_LINTER
# read_only_cache = True              # environment CONAN_READ_ONLY_CACHE
# pylintrc = path/to/pylintrc_file    # environment CONAN_PYLINTRC
# cache_no_locks = True               # environment CONAN_CACHE_NO_LOCKS
# user_home_short = your_path         # environment CONAN_USER_HOME_SHORT
# use_always_short_paths = False      # environment CONAN_USE_ALWAYS_SHORT_PATHS
# skip_vs_projects_upgrade = False    # environment CONAN_SKIP_VS_PROJECTS_UPGRADE
# non_interactive = False             # environment CONAN_NON_INTERACTIVE

# conan_make_program = make           # environment CONAN_MAKE_PROGRAM (overrides the make program used in AutoToolsBuildEnvironment.make)
# conan_cmake_program = cmake         # environment CONAN_CMAKE_PROGRAM (overrides the make program used in CMake.cmake_program)

# cmake_generator                     # environment CONAN_CMAKE_GENERATOR
# cmake generator platform            # environment CONAN_CMAKE_GENERATOR_PLATFORM
# http://www.vtk.org/Wiki/CMake_Cross_Compiling
# cmake_toolchain_file                # environment CONAN_CMAKE_TOOLCHAIN_FILE
# cmake_system_name                   # environment CONAN_CMAKE_SYSTEM_NAME
# cmake_system_version                # environment CONAN_CMAKE_SYSTEM_VERSION
# cmake_system_processor              # environment CONAN_CMAKE_SYSTEM_PROCESSOR
# cmake_find_root_path                # environment CONAN_CMAKE_FIND_ROOT_PATH
# cmake_find_root_path_mode_program   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM
# cmake_find_root_path_mode_library   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY
# cmake_find_root_path_mode_include   # environment CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE

# msbuild_verbosity = minimal         # environment CONAN_MSBUILD_VERBOSITY

# cpu_count = 1             # environment CONAN_CPU_COUNT

# Change the default location for building test packages to a temporary folder
# which is deleted after the test.
# temp_test_folder = True             # environment CONAN_TEMP_TEST_FOLDER

# cacert_path                         # environment CONAN_CACERT_PATH

[storage]
# This is the default path, but you can write your own. It must be an absolute path or a
# path beginning with "~" (if the environment var CONAN_USER_HOME is specified, this directory, even
# with "~/", will be relative to the conan user home, not to the system user home)
path = ~/.conan/data

[proxies]
# Empty section will try to use system proxies.
# If don't want proxy at all, remove section [proxies]
# As documented in http://docs.python-requests.org/en/latest/user/advanced/#proxies
# http = http://user:pass@10.10.1.10:3128/
# http = http://10.10.1.10:3128
# https = http://10.10.1.10:1080
# You can skip the proxy for the matching (fnmatch) urls (comma-separated)
# no_proxy_match = *bintray.com*, https://myserver.*

[hooks]    # environment CONAN_HOOKS
attribute_checker

# Default settings now declared in the default profile


""" % DEFAULT_PROFILE_NAME


class ConanClientConfigParser(ConfigParser, object):

    def __init__(self, filename):
        ConfigParser.__init__(self, allow_no_value=True)
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
               "CONAN_NON_INTERACTIVE": self._env_c("general.non_interactive", "CONAN_NON_INTERACTIVE", "False"),
               "CONAN_PYLINTRC": self._env_c("general.pylintrc", "CONAN_PYLINTRC", None),
               "CONAN_CACHE_NO_LOCKS": self._env_c("general.cache_no_locks", "CONAN_CACHE_NO_LOCKS", "False"),
               "CONAN_PYLINT_WERR": self._env_c("general.pylint_werr", "CONAN_PYLINT_WERR", None),
               "CONAN_SYSREQUIRES_SUDO": self._env_c("general.sysrequires_sudo", "CONAN_SYSREQUIRES_SUDO", "False"),
               "CONAN_SYSREQUIRES_MODE": self._env_c("general.sysrequires_mode", "CONAN_SYSREQUIRES_MODE", "enabled"),
               "CONAN_REQUEST_TIMEOUT": self._env_c("general.request_timeout", "CONAN_REQUEST_TIMEOUT", None),
               "CONAN_VS_INSTALLATION_PREFERENCE": self._env_c("general.vs_installation_preference", "CONAN_VS_INSTALLATION_PREFERENCE", None),
               "CONAN_RECIPE_LINTER": self._env_c("general.recipe_linter", "CONAN_RECIPE_LINTER", "True"),
               "CONAN_CPU_COUNT": self._env_c("general.cpu_count", "CONAN_CPU_COUNT", None),
               "CONAN_READ_ONLY_CACHE": self._env_c("general.read_only_cache", "CONAN_READ_ONLY_CACHE", None),
               "CONAN_USER_HOME_SHORT": self._env_c("general.user_home_short", "CONAN_USER_HOME_SHORT", None),
               "CONAN_USE_ALWAYS_SHORT_PATHS": self._env_c("general.use_always_short_paths", "CONAN_USE_ALWAYS_SHORT_PATHS", None),
               "CONAN_VERBOSE_TRACEBACK": self._env_c("general.verbose_traceback", "CONAN_VERBOSE_TRACEBACK", None),
               "CONAN_ERROR_ON_OVERRIDE": self._env_c("general.error_on_override", "CONAN_ERROR_ON_OVERRIDE", "False"),
               # http://www.vtk.org/Wiki/CMake_Cross_Compiling
               "CONAN_CMAKE_GENERATOR": self._env_c("general.cmake_generator", "CONAN_CMAKE_GENERATOR", None),
               "CONAN_CMAKE_GENERATOR_PLATFORM": self._env_c("general.cmake_generator_platform", "CONAN_CMAKE_GENERATOR_PLATFORM", None),
               "CONAN_CMAKE_TOOLCHAIN_FILE": self._env_c("general.cmake_toolchain_file", "CONAN_CMAKE_TOOLCHAIN_FILE", None),
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
               "CONAN_MAKE_PROGRAM": self._env_c("general.conan_make_program", "CONAN_MAKE_PROGRAM", None),
               "CONAN_CMAKE_PROGRAM": self._env_c("general.conan_cmake_program", "CONAN_CMAKE_PROGRAM", None),
               "CONAN_TEMP_TEST_FOLDER": self._env_c("general.temp_test_folder", "CONAN_TEMP_TEST_FOLDER", "False"),
               "CONAN_SKIP_VS_PROJECTS_UPGRADE": self._env_c("general.skip_vs_projects_upgrade", "CONAN_SKIP_VS_PROJECTS_UPGRADE", "False"),
               "CONAN_HOOKS": self._env_c("hooks", "CONAN_HOOKS", None),
               "CONAN_MSBUILD_VERBOSITY": self._env_c("general.msbuild_verbosity",
                                                      "CONAN_MSBUILD_VERBOSITY",
                                                      None),
               "CONAN_CACERT_PATH": self._env_c("general.cacert_path", "CONAN_CACERT_PATH", None)
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
            if section_name == "hooks":
                for key, _ in section:
                    result.append(key)
                return ",".join(result)
            else:
                for section_item in section:
                    result.append(" = ".join(section_item))
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
        try:
            super(ConanClientConfigParser, self).set(section_name, key, value)
        except ValueError:
            # https://github.com/conan-io/conan/issues/4110
            value = value.replace("%", "%%")
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
    def default_profile(self):
        ret = os.environ.get("CONAN_DEFAULT_PROFILE_PATH", None)
        if ret:
            if not os.path.isabs(ret):
                from conans.client.cache.cache import PROFILES_FOLDER
                profiles_folder = os.path.join(os.path.dirname(self.filename), PROFILES_FOLDER)
                ret = os.path.abspath(os.path.join(profiles_folder, ret))

            if not os.path.exists(ret):
                raise ConanException("Environment variable 'CONAN_DEFAULT_PROFILE_PATH' "
                                     "must point to an existing profile file.")
            return ret
        else:
            try:
                return unquote(self.get_item("general.default_profile"))
            except ConanException:
                return DEFAULT_PROFILE_NAME

    @property
    def cache_no_locks(self):
        try:
            return get_env("CONAN_CACHE_NO_LOCKS", False)
        except ConanException:
            return False

    @property
    def storage(self):
        return dict(self.get_conf("storage"))

    @property
    def request_timeout(self):
        try:
            return self.get_item("general.request_timeout")
        except ConanException:
            return None

    @property
    def revisions_enabled(self):
        try:
            revisions_enabled = get_env("CONAN_REVISIONS_ENABLED")
            if revisions_enabled is None:
                try:
                    revisions_enabled = self.get_item("general.revisions_enabled")
                except ConanException:
                    return False
            return revisions_enabled.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def default_package_id_mode(self):
        try:
            return self.get_item("general.default_package_id_mode")
        except ConanException:
            return "semver_direct_mode"

    @property
    def storage_path(self):
        # Try with CONAN_STORAGE_PATH
        result = get_env('CONAN_STORAGE_PATH', None)

        # Try with conan.conf "path"
        if not result:
            try:
                env_conan_user_home = os.getenv("CONAN_USER_HOME")
                # if env var is declared, any specified path will be relative to CONAN_USER_HOME
                # even with the ~/
                if env_conan_user_home:
                    storage = self.storage["path"]
                    if storage[:2] == "~/":
                        storage = storage[2:]
                    result = os.path.join(env_conan_user_home, storage)
                else:
                    result = self.storage["path"]
            except KeyError:
                pass

        # expand the result and check if absolute
        if result:
            result = conan_expand_user(result)
            if not os.path.isabs(result):
                raise ConanException("Conan storage path has to be an absolute path")
        return result

    @property
    def proxies(self):
        """ optional field, might not exist
        """
        try:
            proxies = self.get_conf("proxies")
            # If there is proxies section, but empty, it will try to use system proxy
            if not proxies:
                # We don't have evidences that this following line is necessary.
                # If the proxies has been
                # configured at system level, conan will use it, and shouldn't be necessary
                # to return here the proxies read from the system.
                # Furthermore, the urls excluded for use proxies at system level do not work in
                # this case, then the only way is to remove the [proxies] section with
                # conan config remote proxies, then this method will return None and the proxies
                # dict passed to requests will be empty.
                # We don't remove this line because we are afraid to break something, but maybe
                # until now is working because no one is using system-wide proxies or those proxies
                # rules don't contain excluded urls.c #1777
                return urllib.request.getproxies()
            result = {k: (None if v == "None" else v) for k, v in proxies}
            return result
        except:
            return None

    @property
    def cacert_path(self):
        try:
            cacert_path = get_env("CONAN_CACERT_PATH")
            if not cacert_path:
                cacert_path = self.get_item("general.cacert_path")
        except ConanException:
            cacert_path = os.path.join(os.path.dirname(self.filename), CACERT_FILE)
        else:
            # For explicit cacert files, the file should already exist
            if not os.path.exists(cacert_path):
                raise ConanException("Configured file for 'cacert_path'"
                                     " doesn't exists: '{}'".format(cacert_path))
        return cacert_path
