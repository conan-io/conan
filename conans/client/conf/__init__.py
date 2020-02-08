import os

from six.moves.configparser import ConfigParser, NoSectionError

from conans.errors import ConanException
from conans.model.env_info import unquote
from conans.paths import DEFAULT_PROFILE_NAME, conan_expand_user, CACERT_FILE
from conans.util.env_reader import get_env
from conans.util.files import load
import logging


default_settings_yml = """
# Only for cross building, 'os_build/arch_build' is the system that runs Conan
os_build: [Windows, WindowsStore, Linux, Macos, FreeBSD, SunOS, AIX]
arch_build: [x86, x86_64, ppc32be, ppc32, ppc64le, ppc64, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x, sh4le]

# Only for building cross compilation tools, 'os_target/arch_target' is the system for
# which the tools generate code
os_target: [Windows, Linux, Macos, Android, iOS, watchOS, tvOS, FreeBSD, SunOS, AIX, Arduino, Neutrino]
arch_target: [x86, x86_64, ppc32be, ppc32, ppc64le, ppc64, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x, asm.js, wasm, sh4le]

# Rest of the settings are "host" settings:
# - For native building/cross building: Where the library/program will run.
# - For building cross compilation tools: Where the cross compiler will run.
os:
    Windows:
        subsystem: [None, cygwin, msys, msys2, wsl]
    WindowsStore:
        version: ["8.1", "10.0"]
    WindowsCE:
        platform: ANY
        version: ["5.0", "6.0", "7.0", "8.0"]
    Linux:
    Macos:
        version: [None, "10.6", "10.7", "10.8", "10.9", "10.10", "10.11", "10.12", "10.13", "10.14", "10.15"]
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3", "11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4", "13.0", "13.1"]
    watchOS:
        version: ["4.0", "4.1", "4.2", "4.3", "5.0", "5.1", "5.2", "5.3", "6.0", "6.1"]
    tvOS:
        version: ["11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4", "13.0"]
    FreeBSD:
    SunOS:
    AIX:
    Arduino:
        board: ANY
    Emscripten:
    Neutrino:
        version: ["6.4", "6.5", "6.6", "7.0"]
arch: [x86, x86_64, ppc32be, ppc32, ppc64le, ppc64, armv4, armv4i, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x, asm.js, wasm, sh4le]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14"]
        threads: [None, posix]
        libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc: &gcc
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                  "5", "5.1", "5.2", "5.3", "5.4", "5.5",
                  "6", "6.1", "6.2", "6.3", "6.4",
                  "7", "7.1", "7.2", "7.3", "7.4",
                  "8", "8.1", "8.2", "8.3",
                  "9", "9.1", "9.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32] #  Windows MinGW
        exception: [None, dwarf2, sjlj, seh] # Windows MinGW
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
    Visual Studio: &visual_studio
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15", "16"]
        toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp,
                  v140, v140_xp, v140_clang_c2, LLVM-vs2012, LLVM-vs2012_xp,
                  LLVM-vs2013, LLVM-vs2013_xp, LLVM-vs2014, LLVM-vs2014_xp,
                  LLVM-vs2017, LLVM-vs2017_xp, v141, v141_xp, v141_clang_c2, v142]
        cppstd: [None, 14, 17, 20]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0",
                  "5.0", "6.0", "7.0", "7.1",
                  "8", "9", "10"]
        libcxx: [libstdc++, libstdc++11, libc++, c++_shared, c++_static]
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
    apple-clang:
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0", "9.1", "10.0", "11.0"]
        libcxx: [libstdc++, libc++]
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
    intel:
        version: ["11", "12", "13", "14", "15", "16", "17", "18", "19"]
        base:
            gcc:
                <<: *gcc
                threads: [None]
                exception: [None]
            Visual Studio:
                <<: *visual_studio
    qcc:
        version: ["4.4", "5.4"]
        libcxx: [cxx, gpp, cpp, cpp-ne, accp, acpp-ne, ecpp, ecpp-ne]

build_type: [None, Debug, Release, RelWithDebInfo, MinSizeRel]
cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]  # Deprecated, use compiler.cppstd
"""

default_client_conf = """
[log]
run_to_output = True        # environment CONAN_LOG_RUN_TO_OUTPUT
run_to_file = False         # environment CONAN_LOG_RUN_TO_FILE
level = critical            # environment CONAN_LOGGING_LEVEL
# trace_file =              # environment CONAN_TRACE_FILE
print_run_commands = False  # environment CONAN_PRINT_RUN_COMMANDS

[general]
default_profile = %s
compression_level = 9                 # environment CONAN_COMPRESSION_LEVEL
sysrequires_sudo = True               # environment CONAN_SYSREQUIRES_SUDO
request_timeout = 60                  # environment CONAN_REQUEST_TIMEOUT (seconds)
default_package_id_mode = semver_direct_mode # environment CONAN_DEFAULT_PACKAGE_ID_MODE
# retry = 2                             # environment CONAN_RETRY
# retry_wait = 5                        # environment CONAN_RETRY_WAIT (seconds)
# sysrequires_mode = enabled          # environment CONAN_SYSREQUIRES_MODE (allowed modes enabled/verify/disabled)
# vs_installation_preference = Enterprise, Professional, Community, BuildTools # environment CONAN_VS_INSTALLATION_PREFERENCE
# verbose_traceback = False           # environment CONAN_VERBOSE_TRACEBACK
# error_on_override = False           # environment CONAN_ERROR_ON_OVERRIDE
# bash_path = ""                      # environment CONAN_BASH_PATH (only windows)
# read_only_cache = True              # environment CONAN_READ_ONLY_CACHE
# cache_no_locks = True               # environment CONAN_CACHE_NO_LOCKS
# user_home_short = your_path         # environment CONAN_USER_HOME_SHORT
# use_always_short_paths = False      # environment CONAN_USE_ALWAYS_SHORT_PATHS
# skip_vs_projects_upgrade = False    # environment CONAN_SKIP_VS_PROJECTS_UPGRADE
# non_interactive = False             # environment CONAN_NON_INTERACTIVE
# skip_broken_symlinks_check = False  # enviornment CONAN_SKIP_BROKEN_SYMLINKS_CHECK

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
# scm_to_conandata                    # environment CONAN_SCM_TO_CONANDATA

[storage]
# This is the default path, but you can write your own. It must be an absolute path or a
# path beginning with "~" (if the environment var CONAN_USER_HOME is specified, this directory, even
# with "~/", will be relative to the conan user home, not to the system user home)
path = ./data

[proxies]
# Empty (or missing) section will try to use system proxies.
# As documented in https://requests.readthedocs.io/en/master/user/advanced/#proxies - but see below
# for proxies to specific hosts
# http = http://user:pass@10.10.1.10:3128/
# http = http://10.10.1.10:3128
# https = http://10.10.1.10:1080
# To specify a proxy for a specific host or hosts, use multiple lines each specifying host = proxy-spec
# http =
#   hostname.to.be.proxied.com = http://user:pass@10.10.1.10:3128
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
               "CONAN_SKIP_BROKEN_SYMLINKS_CHECK": self._env_c("general.skip_broken_symlinks_check", "CONAN_SKIP_BROKEN_SYMLINKS_CHECK", "False"),
               "CONAN_CACHE_NO_LOCKS": self._env_c("general.cache_no_locks", "CONAN_CACHE_NO_LOCKS", "False"),
               "CONAN_SYSREQUIRES_SUDO": self._env_c("general.sysrequires_sudo", "CONAN_SYSREQUIRES_SUDO", "False"),
               "CONAN_SYSREQUIRES_MODE": self._env_c("general.sysrequires_mode", "CONAN_SYSREQUIRES_MODE", "enabled"),
               "CONAN_REQUEST_TIMEOUT": self._env_c("general.request_timeout", "CONAN_REQUEST_TIMEOUT", None),
               "CONAN_RETRY": self._env_c("general.retry", "CONAN_RETRY", None),
               "CONAN_RETRY_WAIT": self._env_c("general.retry_wait", "CONAN_RETRY_WAIT", None),
               "CONAN_VS_INSTALLATION_PREFERENCE": self._env_c("general.vs_installation_preference", "CONAN_VS_INSTALLATION_PREFERENCE", None),
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
               "CONAN_CACERT_PATH": self._env_c("general.cacert_path", "CONAN_CACERT_PATH", None),
               "CONAN_DEFAULT_PACKAGE_ID_MODE": self._env_c("general.default_package_id_mode",
                                                            "CONAN_DEFAULT_PACKAGE_ID_MODE", None),
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
    def request_timeout(self):
        timeout = os.getenv("CONAN_REQUEST_TIMEOUT")
        if not timeout:
            try:
                timeout = self.get_item("general.request_timeout")
            except ConanException:
                return None

        try:
            return float(timeout) if timeout is not None else None
        except ValueError:
            raise ConanException("Specify a numeric parameter for 'request_timeout'")

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
    def download_cache(self):
        try:
            download_cache = self.get_item("storage.download_cache")
            return download_cache
        except ConanException:
            return None

    @property
    def scm_to_conandata(self):
        try:
            scm_to_conandata = get_env("CONAN_SCM_TO_CONANDATA")
            if scm_to_conandata is None:
                scm_to_conandata = self.get_item("general.scm_to_conandata")
            return scm_to_conandata.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def default_package_id_mode(self):
        try:
            default_package_id_mode = get_env("CONAN_DEFAULT_PACKAGE_ID_MODE")
            if default_package_id_mode is None:
                default_package_id_mode = self.get_item("general.default_package_id_mode")
        except ConanException:
            return "semver_direct_mode"
        return default_package_id_mode

    @property
    def default_python_requires_id_mode(self):
        try:
            default_package_id_mode = get_env("CONAN_DEFAULT_PYTHON_REQUIRES_ID_MODE")
            if default_package_id_mode is None:
                default_package_id_mode = self.get_item("general.default_python_requires_id_mode")
        except ConanException:
            return "minor_mode"
        return default_package_id_mode

    @property
    def short_paths_home(self):
        short_paths_home = get_env("CONAN_USER_HOME_SHORT")
        if short_paths_home:
            current_dir = os.path.dirname(os.path.normpath(os.path.normcase(self.filename)))
            short_paths_dir = os.path.normpath(os.path.normcase(short_paths_home))
            if current_dir == short_paths_dir  or \
                    short_paths_dir.startswith(current_dir + os.path.sep):
                raise ConanException("Short path home '{}' (defined by conan.conf variable "
                                     "'user_home_short', or environment variable "
                                     "'CONAN_USER_HOME_SHORT') cannot be a subdirectory of "
                                     "the conan cache '{}'.".format(short_paths_home, current_dir))
        return short_paths_home

    @property
    def storage_path(self):
        # Try with CONAN_STORAGE_PATH
        result = get_env('CONAN_STORAGE_PATH', None)
        if not result:
            # Try with conan.conf "path"
            try:
                # TODO: Fix this mess for Conan 2.0
                env_conan_user_home = os.getenv("CONAN_USER_HOME")
                current_dir = os.path.dirname(self.filename)
                # if env var is declared, any specified path will be relative to CONAN_USER_HOME
                # even with the ~/
                result = dict(self.get_conf("storage"))["path"]
                if result.startswith("."):
                    result = os.path.abspath(os.path.join(current_dir, result))
                elif result[:2] == "~/":
                    if env_conan_user_home:
                        result = os.path.join(env_conan_user_home, result[2:])
            except (KeyError, ConanException):  # If storage not defined, to return None
                pass

        if result:
            result = conan_expand_user(result)
            if not os.path.isabs(result):
                raise ConanException("Conan storage path has to be an absolute path")
        return result

    @property
    def proxies(self):
        try:  # optional field, might not exist
            proxies = self.get_conf("proxies")
        except Exception:
            return None
        result = {}
        # Handle proxy specifications of the form:
        # http = http://proxy.xyz.com
        #   special-host.xyz.com = http://special-proxy.xyz.com
        # (where special-proxy.xyz.com is only used as a proxy when special-host.xyz.com)
        for scheme, proxy_string in proxies or []:
            if proxy_string is None or proxy_string == "None":
                result[scheme] = None
            else:
                for line in proxy_string.splitlines():
                    proxy_value = [t.strip() for t in line.split("=", 1)]
                    if len(proxy_value) == 2:
                        result[scheme+"://"+proxy_value[0]] = proxy_value[1]
                    elif proxy_value[0]:
                        result[scheme] = proxy_value[0]
        return result

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

    @property
    def client_cert_path(self):
        # TODO: Really parameterize the client cert location
        folder = os.path.dirname(self.filename)
        CLIENT_CERT = "client.crt"
        return os.path.normpath(os.path.join(folder, CLIENT_CERT))

    @property
    def client_cert_key_path(self):
        CLIENT_KEY = "client.key"
        folder = os.path.dirname(self.filename)
        return os.path.normpath(os.path.join(folder, CLIENT_KEY))

    @property
    def hooks(self):
        hooks = get_env("CONAN_HOOKS", list())
        if not hooks:
            try:
                hooks = self.get_conf("hooks")
                hooks = [k for k, _ in hooks]
            except Exception:
                hooks = []
        return hooks

    @property
    def non_interactive(self):
        try:
            non_interactive = get_env("CONAN_NON_INTERACTIVE")
            if non_interactive is None:
                non_interactive = self.get_item("general.non_interactive")
            return non_interactive.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def logging_level(self):
        try:
            level = get_env("CONAN_LOGGING_LEVEL")
            if level is None:
                level = self.get_item("log.level")
            try:
                parsed_level = ConanClientConfigParser.get_log_level_by_name(level)
                level = parsed_level if parsed_level is not None else int(level)
            except Exception:
                level = logging.CRITICAL
            return level
        except ConanException:
            return logging.CRITICAL

    @property
    def logging_file(self):
        return get_env('CONAN_LOGGING_FILE', None)

    @property
    def print_commands_to_output(self):
        try:
            print_commands_to_output = get_env("CONAN_PRINT_RUN_COMMANDS")
            if print_commands_to_output is None:
                print_commands_to_output = self.get_item("log.print_run_commands")
            return print_commands_to_output.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def retry(self):
        retry = os.getenv("CONAN_RETRY")
        if not retry:
            try:
                retry = self.get_item("general.retry")
            except ConanException:
                return None

        try:
            return int(retry) if retry is not None else None
        except ValueError:
            raise ConanException("Specify a numeric parameter for 'retry'")

    @property
    def retry_wait(self):
        retry_wait = os.getenv("CONAN_RETRY_WAIT")
        if not retry_wait:
            try:
                retry_wait = self.get_item("general.retry_wait")
            except ConanException:
                return None

        try:
            return int(retry_wait) if retry_wait is not None else None
        except ValueError:
            raise ConanException("Specify a numeric parameter for 'retry_wait'")

    @property
    def generate_run_log_file(self):
        try:
            generate_run_log_file = get_env("CONAN_LOG_RUN_TO_FILE")
            if generate_run_log_file is None:
                generate_run_log_file = self.get_item("log.run_to_file")
            return generate_run_log_file.lower() in ("1", "true")
        except ConanException:
            return False

    @property
    def log_run_to_output(self):
        try:
            log_run_to_output = get_env("CONAN_LOG_RUN_TO_OUTPUT")
            if log_run_to_output is None:
                log_run_to_output = self.get_item("log.run_to_output")
            return log_run_to_output.lower() in ("1", "true")
        except ConanException:
            return True

    @staticmethod
    def get_log_level_by_name(level_name):
        levels = {
            "critical": logging.CRITICAL,
            "error": logging.ERROR,
            "warning": logging.WARNING,
            "warn": logging.WARNING,
            "info": logging.INFO,
            "debug": logging.DEBUG,
            "notset": logging.NOTSET
        }
        return levels.get(str(level_name).lower())