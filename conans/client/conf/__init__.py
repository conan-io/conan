import logging
import textwrap
from configparser import ConfigParser, NoSectionError

from conans.errors import ConanException
from conans.util.env import get_env
from conans.util.files import load

default_settings_yml = """\
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
        version: [None, "10.6", "10.7", "10.8", "10.9", "10.10", "10.11", "10.12", "10.13", "10.14", "10.15", "11.0", "12.0", "13.0"]
        sdk: [None, "macosx"]
        subsystem: [None, catalyst]
    Android:
        api_level: ANY
    iOS:
        version: ["7.0", "7.1", "8.0", "8.1", "8.2", "8.3", "9.0", "9.1", "9.2", "9.3", "10.0", "10.1", "10.2", "10.3",
                  "11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4",
                  "13.0", "13.1", "13.2", "13.3", "13.4", "13.5", "13.6", "13.7",
                  "14.0", "14.1", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7", "14.8", "15.0", "15.1"]
        sdk: [None, "iphoneos", "iphonesimulator"]
    watchOS:
        version: ["4.0", "4.1", "4.2", "4.3", "5.0", "5.1", "5.2", "5.3", "6.0", "6.1", "6.2",
                  "7.0", "7.1", "7.2", "7.3", "7.4", "7.5", "7.6", "8.0", "8.1"]
        sdk: [None, "watchos", "watchsimulator"]
    tvOS:
        version: ["11.0", "11.1", "11.2", "11.3", "11.4", "12.0", "12.1", "12.2", "12.3", "12.4",
                  "13.0", "13.2", "13.3", "13.4", "14.0", "14.2", "14.3", "14.4", "14.5", "14.6", "14.7",
                  "15.0", "15.1"]
        sdk: [None, "appletvos", "appletvsimulator"]
    FreeBSD:
    SunOS:
    AIX:
    Arduino:
        board: ANY
    Emscripten:
    Neutrino:
        version: ["6.4", "6.5", "6.6", "7.0", "7.1"]
    baremetal:
arch: [x86, x86_64, ppc32be, ppc32, ppc64le, ppc64, armv4, armv4i, armv5el, armv5hf, armv6, armv7, armv7hf, armv7s, armv7k, armv8, armv8_32, armv8.3, sparc, sparcv9, mips, mips64, avr, s390, s390x, asm.js, wasm, sh4le, e2k-v2, e2k-v3, e2k-v4, e2k-v5, e2k-v6, e2k-v7, xtensalx6, xtensalx106]
compiler:
    sun-cc:
        version: ["5.10", "5.11", "5.12", "5.13", "5.14", "5.15"]
        threads: [None, posix]
        libcxx: [libCstd, libstdcxx, libstlport, libstdc++]
    gcc: &gcc
        version: ["4.1", "4.4", "4.5", "4.6", "4.7", "4.8", "4.9",
                  "5", "5.1", "5.2", "5.3", "5.4", "5.5",
                  "6", "6.1", "6.2", "6.3", "6.4", "6.5",
                  "7", "7.1", "7.2", "7.3", "7.4", "7.5",
                  "8", "8.1", "8.2", "8.3", "8.4",
                  "9", "9.1", "9.2", "9.3",
                  "10", "10.1", "10.2", "10.3",
                  "11", "11.1", "11.2"]
        libcxx: [libstdc++, libstdc++11]
        threads: [None, posix, win32]  # Windows MinGW
        exception: [None, dwarf2, sjlj, seh]  # Windows MinGW
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
    Visual Studio: &visual_studio
        runtime: [MD, MT, MTd, MDd]
        version: ["8", "9", "10", "11", "12", "14", "15", "16", "17"]
        toolset: [None, v90, v100, v110, v110_xp, v120, v120_xp,
                  v140, v140_xp, v140_clang_c2, LLVM-vs2012, LLVM-vs2012_xp,
                  LLVM-vs2013, LLVM-vs2013_xp, LLVM-vs2014, LLVM-vs2014_xp,
                  LLVM-vs2017, LLVM-vs2017_xp, v141, v141_xp, v141_clang_c2, v142,
                  llvm, ClangCL, v143]
        cppstd: [None, 14, 17, 20, 23]
    msvc:
        version: [190, 191, 192, 193]
        update: [None, 0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        runtime: [static, dynamic]
        runtime_type: [Debug, Release]
        cppstd: [14, 17, 20, 23]
    clang:
        version: ["3.3", "3.4", "3.5", "3.6", "3.7", "3.8", "3.9", "4.0",
                  "5.0", "6.0", "7.0", "7.1",
                  "8", "9", "10", "11", "12", "13", "14"]
        libcxx: [None, libstdc++, libstdc++11, libc++, c++_shared, c++_static]
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
        runtime: [None, MD, MT, MTd, MDd]
    apple-clang: &apple_clang
        version: ["5.0", "5.1", "6.0", "6.1", "7.0", "7.3", "8.0", "8.1", "9.0", "9.1", "10.0", "11.0", "12.0", "13.0"]
        libcxx: [libstdc++, libc++]
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20]
    intel:
        version: ["11", "12", "13", "14", "15", "16", "17", "18", "19", "19.1"]
        update: [None, ANY]
        base:
            gcc:
                <<: *gcc
                threads: [None]
                exception: [None]
            Visual Studio:
                <<: *visual_studio
            apple-clang:
                <<: *apple_clang
    intel-cc:
        version: ["2021.1", "2021.2", "2021.3"]
        update: [None, ANY]
        mode: ["icx", "classic", "dpcpp"]
        libcxx: [None, libstdc++, libstdc++11, libc++]
        cppstd: [None, 98, gnu98, 03, gnu03, 11, gnu11, 14, gnu14, 17, gnu17, 20, gnu20, 23, gnu23]
        runtime: [None, static, dynamic]
        runtime_type: [None, Debug, Release]
    qcc:
        version: ["4.4", "5.4", "8.3"]
        libcxx: [cxx, gpp, cpp, cpp-ne, accp, acpp-ne, ecpp, ecpp-ne]
        cppstd: [None, 98, gnu98, 11, gnu11, 14, gnu14, 17, gnu17]
    mcst-lcc:
        version: ["1.19", "1.20", "1.21", "1.22", "1.23", "1.24", "1.25"]
        base:
            gcc:
                <<: *gcc
                threads: [None]
                exceptions: [None]

build_type: [None, Debug, Release, RelWithDebInfo, MinSizeRel]
"""


def get_default_settings_yml():
    return default_settings_yml


_t_default_client_conf = textwrap.dedent("""
    [log]
    run_to_output = True        # environment CONAN_LOG_RUN_TO_OUTPUT
    run_to_file = False         # environment CONAN_LOG_RUN_TO_FILE
    level = critical            # environment CONAN_LOGGING_LEVEL
    # trace_file =              # environment CONAN_TRACE_FILE
    print_run_commands = False  # environment CONAN_PRINT_RUN_COMMANDS

    [general]
    sysrequires_sudo = True               # environment CONAN_SYSREQUIRES_SUDO

    # sysrequires_mode = enabled          # environment CONAN_SYSREQUIRES_MODE (allowed modes enabled/verify/disabled)
    # verbose_traceback = False           # environment CONAN_VERBOSE_TRACEBACK

    # skip_broken_symlinks_check = False  # environment CONAN_SKIP_BROKEN_SYMLINKS_CHECK

    # cpu_count = 1             # environment CONAN_CPU_COUNT

    # Change the default location for building test packages to a temporary folder
    # which is deleted after the test.
    # temp_test_folder = True             # environment CONAN_TEMP_TEST_FOLDER

    [storage]
    # This is the default path, but you can write your own. It must be an absolute path or a
    # path beginning with "~" (if the environment var CONAN_HOME is specified, this directory, even
    # with "~/", will be relative to the conan user home, not to the system user home)
    path = ./data
    """)


def get_default_client_conf():
    return _t_default_client_conf


class ConanClientConfigParser(ConfigParser, object):

    # So keys are not converted to lowercase, we override the default optionxform
    optionxform = str

    def __init__(self, filename):
        super(ConanClientConfigParser, self).__init__(allow_no_value=True)
        self.read(filename)
        self.filename = filename

    def get_item(self, item):
        """ Return the value stored in 'conan.conf' """
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

    def _get_conf(self, varname):
        """Gets the section from config file or raises an exception"""
        try:
            return self.items(varname)
        except NoSectionError:
            raise ConanException("Invalid configuration, missing %s" % varname)

    @property
    def hooks(self):
        hooks = get_env("CONAN_HOOKS", list())
        if not hooks:
            try:
                hooks = self._get_conf("hooks")
                hooks = [k for k, _ in hooks]
            except Exception:
                hooks = []
        return hooks

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
