from collections import OrderedDict
from contextlib import contextmanager

from conans.errors import ConanException
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.util.env_reader import get_env
from conans.util.files import mkdir
from conans.tools import cpu_count, args_to_string
from conans import tools
import os
import platform
from conans.util.log import logger

# Deprecated in 0.22
deprecated_conanfile_param_message = '''
*******************************   WARNING!!! ************************************

Do not pass 'self' to configure() nor build() methods, it is deprecated and will be removed.

Instance CMake with the conanfile instance instead:

    cmake = CMake(self)
    cmake.configure() # Optional args, defs, source_dir and build_dir parameters
    cmake.build() # Optional args, build_dir and target


**********************************************************************************
'''


def _get_env_cmake_system_name():
    env_system_name = get_env("CONAN_CMAKE_SYSTEM_NAME", "")
    return {"False": False, "True": True, "": None}.get(env_system_name, env_system_name)


class CMake(object):

    def __init__(self, settings_or_conanfile, generator=None, cmake_system_name=True, parallel=True):
        """

        :param settings_or_conanfile: Conanfile instance (or settings for retro compatibility)
        :param generator: Generator name to use or none to autodetect
        :param cmake_system_name: False to not use CMAKE_SYSTEM_NAME variable, True for auto-detect or directly a string
               with the system name
        :param parallel: Try to build with multiple cores if available
        """
        if isinstance(settings_or_conanfile, Settings):
            self._settings = settings_or_conanfile
            self._conanfile = None
            self.configure = self._configure_old
            self.build = self._build_old
        elif isinstance(settings_or_conanfile, ConanFile):
            self._settings = settings_or_conanfile.settings
            self._conanfile = settings_or_conanfile
            self.configure = self._configure_new
            self.build = self._build_new
        else:
            raise ConanException("First parameter of CMake() has to be a ConanFile instance.")

        self._os = self._settings.get_safe("os")
        self._compiler = self._settings.get_safe("compiler")
        self._compiler_version = self._settings.get_safe("compiler.version")
        self._arch = self._settings.get_safe("arch")
        self._build_type = self._settings.get_safe("build_type")
        self._op_system_version = self._settings.get_safe("os.version")
        self._libcxx = self._settings.get_safe("compiler.libcxx")
        self._runtime = self._settings.get_safe("compiler.runtime")

        self.generator = generator or self._generator()
        self.build_dir = None
        self._cmake_system_name = _get_env_cmake_system_name()
        if self._cmake_system_name is None:  # Not overwritten using environment
            self._cmake_system_name = cmake_system_name
        self.parallel = parallel
        self.definitions = self._get_cmake_definitions()

    @property
    def flags(self):
        return _defs_to_string(self.definitions)

    @staticmethod
    def options_cmd_line(options, option_upper=True, value_upper=True):
        """ FIXME: this function seems weird, not tested, not used.
        Probably should be deprecated
        """
        result = []
        for option, value in options.values.as_list():
            if value is not None:
                option = option.upper() if option_upper else option
                value = value.upper() if value_upper else value
                result.append("-D%s=%s" % (option, value))
        return ' '.join(result)

    def _generator(self):

        if not self._compiler or not self._compiler_version or not self._arch:
            raise ConanException("You must specify compiler, compiler.version and arch in "
                                 "your settings to use a CMake generator")

        if "CONAN_CMAKE_GENERATOR" in os.environ:
            return os.environ["CONAN_CMAKE_GENERATOR"]

        if self._compiler == "Visual Studio":
            _visuals = {'8': '8 2005',
                        '9': '9 2008',
                        '10': '10 2010',
                        '11': '11 2012',
                        '12': '12 2013',
                        '14': '14 2015',
                        '15': '15 2017'}
            base = "Visual Studio %s" % _visuals.get(self._compiler_version, "UnknownVersion %s" % self._compiler_version)
            if self._arch == "x86_64":
                return base + " Win64"
            elif "arm" in self._arch:
                return base + " ARM"
            else:
                return base

        if self._os == "Windows":
            return "MinGW Makefiles"  # it is valid only under Windows

        return "Unix Makefiles"

    def _cmake_compiler_options(self, the_os, arch):
        cmake_definitions = OrderedDict()

        if str(the_os).lower() == "macos":
            if arch == "x86":
                cmake_definitions["CMAKE_OSX_ARCHITECTURES"] = "i386"
        return cmake_definitions

    def _cmake_cross_build_defines(self, the_os, os_ver):
        ret = OrderedDict()
        os_ver = get_env("CONAN_CMAKE_SYSTEM_VERSION", os_ver)

        if self._cmake_system_name is False:
            return ret

        if self._cmake_system_name is not True:  # String not empty
            ret["CMAKE_SYSTEM_NAME"] = self._cmake_system_name
            ret["CMAKE_SYSTEM_VERSION"] = os_ver
        else:  # self._cmake_system_name is True, so detect if we are cross building and the system name and version
            platform_os = {"Darwin": "Macos"}.get(platform.system(), platform.system())
            if (platform_os != the_os) or os_ver:  # We are cross building
                if the_os:
                    ret["CMAKE_SYSTEM_NAME"] = the_os
                    if os_ver:
                        ret["CMAKE_SYSTEM_VERSION"] = os_ver
                else:
                    ret["CMAKE_SYSTEM_NAME"] = "Generic"

        if ret:  # If enabled cross compile
            for env_var in ["CONAN_CMAKE_SYSTEM_PROCESSOR",
                            "CONAN_CMAKE_FIND_ROOT_PATH",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE"]:

                value = os.getenv(env_var, None)
                if value:
                    ret[env_var] = value

            if self._conanfile and self._conanfile.deps_cpp_info.sysroot:
                sysroot_path = self._conanfile.deps_cpp_info.sysroot
            else:
                sysroot_path = os.getenv("CONAN_CMAKE_FIND_ROOT_PATH", None)

            if sysroot_path:
                # Needs to be set here, can't be managed in the cmake generator, CMake needs to know about
                # the sysroot before any other thing
                ret["CMAKE_SYSROOT"] = sysroot_path.replace("\\", "/")

            # Adjust Android stuff
            if self._os == "Android":
                arch_abi_settings = {"armv8": "arm64-v8a",
                                     "armv7": "armeabi-v7a",
                                     "armv7hf": "armeabi-v7a",
                                     "armv6": "armeabi-v6",
                                     "armv5": "armeabi"
                                     }.get(self._arch,
                                           self._arch)
                if arch_abi_settings:
                    ret["CMAKE_ANDROID_ARCH_ABI"] = arch_abi_settings

        logger.info("Setting Cross build flags: %s" % ", ".join(["%s=%s" % (k, v) for k, v in ret.items()]))
        return ret

    @property
    def is_multi_configuration(self):
        """ some IDEs are multi-configuration, as Visual. Makefiles or Ninja are single-conf
        """
        if "Visual" in self.generator or "Xcode" in self.generator:
            return True
        # TODO: complete logic
        return False

    @property
    def command_line(self):
        return _join_arguments([
            '-G "%s"' % self.generator,
            self.flags,
            '-Wno-dev'
        ])

    @property
    def build_type(self):
        return self._defs_to_string(self._build_type_definition())

    def _build_type_definition(self):
        if self._build_type and not self.is_multi_configuration:
            return {'CMAKE_BUILD_TYPE': self._build_type}
        return {}

    @property
    def runtime(self):
        return self._defs_to_string(self._runtime_definition())

    def _runtime_definition(self):
        if self._runtime:
            return {"CONAN_LINK_RUNTIME": "/%s" % self._runtime}
        return {}

    @property
    def build_config(self):
        """ cmake --build tool have a --config option for Multi-configuration IDEs
        """
        if self._build_type and self.is_multi_configuration:
            return "--config %s" % self._build_type
        return ""

    def _get_cmake_definitions(self):
        ret = OrderedDict()
        ret.update(self._build_type_definition())
        ret.update(self._runtime_definition())
        ret.update(self._cmake_compiler_options(the_os=self._os,  arch=self._arch))
        ret.update(self._cmake_cross_build_defines(the_os=self._os, os_ver=self._op_system_version))

        ret["CONAN_EXPORTED"] = "1"
        if self._compiler:
            ret["CONAN_COMPILER"] = self._compiler
        if self._compiler_version:
            ret["CONAN_COMPILER_VERSION"] = str(self._compiler_version)

        # Force compiler flags -- TODO: give as environment/setting parameter?
        if self._os in ("Linux", "FreeBSD", "SunOS"):
            if self._arch == "x86" or self._arch == "sparc":
                ret["CONAN_CXX_FLAGS"] = "-m32"
                ret["CONAN_SHARED_LINKER_FLAGS"] = "-m32"
                ret["CONAN_C_FLAGS"] = "-m32"

            if self._arch == "x86_64" or self._arch == "sparcv9":
                ret["CONAN_CXX_FLAGS"] = "-m64"
                ret["CONAN_SHARED_LINKER_FLAGS"] = "-m64"
                ret["CONAN_C_FLAGS"] = "-m64"

        if self._libcxx:
            ret["CONAN_LIBCXX"] = self._libcxx

        # Shared library
        try:
            ret["BUILD_SHARED_LIBS"] = "ON" if self._conanfile.options.shared else "OFF"
        except:
            pass

        if self._os == "Windows" and self._compiler == "Visual Studio":
            if self.parallel:
                cpus = tools.cpu_count()
                ret["CONAN_CXX_FLAGS"] = "/MP%s" % cpus
                ret["CONAN_C_FLAGS"] = "/MP%s" % cpus
        return ret

    def _configure_old(self, conanfile, args=None, defs=None, source_dir=None, build_dir=None):
        """Deprecated in 0.22"""
        if not isinstance(conanfile, ConanFile):
            raise ConanException(deprecated_conanfile_param_message)
        self._conanfile = conanfile
        self._conanfile.output.warn(deprecated_conanfile_param_message)
        return self._configure_new(args=args, defs=defs, source_dir=source_dir, build_dir=build_dir)

    def _configure_new(self, args=None, defs=None, source_dir=None, build_dir=None):
        if isinstance(args, ConanFile):
            raise ConanException(deprecated_conanfile_param_message)
        args = args or []
        defs = defs or {}
        source_dir = source_dir or self._conanfile.source_folder
        self.build_dir = build_dir or self.build_dir or self._conanfile.build_folder

        mkdir(self.build_dir)
        arg_list = _join_arguments([
            self.command_line,
            args_to_string(args),
            _defs_to_string(defs),
            args_to_string([source_dir])
        ])
        command = "cd %s && cmake %s" % (args_to_string([self.build_dir]), arg_list)
        if platform.system() == "Windows" and self.generator == "MinGW Makefiles":
            with clean_sh_from_path():
                self._conanfile.run(command)
        else:
            self._conanfile.run(command)

    def _build_old(self, conanfile, args=None, build_dir=None, target=None):
        """Deprecated in 0.22"""
        if not isinstance(conanfile, ConanFile):
            raise ConanException(deprecated_conanfile_param_message)
        self._conanfile = conanfile
        self._conanfile.output.warn(deprecated_conanfile_param_message)
        return self._build_new(args=args, build_dir=build_dir, target=target)

    def _build_new(self, args=None, build_dir=None, target=None):
        if isinstance(args, ConanFile):
            raise ConanException(deprecated_conanfile_param_message)
        args = args or []
        build_dir = build_dir or self.build_dir or self._conanfile.build_folder
        if target is not None:
            args = ["--target", target] + args

        if self.parallel:
            if "Makefiles" in self.generator:
                if "--" not in args:
                    args.append("--")
                args.append("-j%i" % cpu_count())

        arg_list = _join_arguments([
            args_to_string([build_dir]),
            self.build_config,
            args_to_string(args)
        ])
        command = "cmake --build %s" % arg_list
        self._conanfile.run(command)

    def test(self, args=None, build_dir=None, target=None):
        if isinstance(args, ConanFile):
            raise ConanException(deprecated_conanfile_param_message)
        if not target:
            target = "RUN_TESTS" if self._compiler == "Visual Studio" else "test"
        self._build_new(args=args, build_dir=build_dir, target=target)


def _defs_to_string(defs):
    return " ".join(['-D{0}="{1}"'.format(k, v) for k, v in defs.items()])


def _join_arguments(args):
    return " ".join(filter(None, args))


@contextmanager
def clean_sh_from_path():
    new_path = []
    for path_entry in os.environ.get("PATH", "").split(os.pathsep):
        if not os.path.exists(os.path.join(path_entry, "sh.exe")):
            new_path.append(path_entry)
    with tools.environment_append({"PATH": os.pathsep.join(new_path)}):
        yield
