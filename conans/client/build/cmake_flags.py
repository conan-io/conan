import os
from collections import OrderedDict

from conans import tools
from conans.client.build.compiler_flags import architecture_flag, parallel_compiler_cl_flag
from conans.client.build.cppstd_flags import cppstd_flag
from conans.client.tools import cross_building
from conans.client.tools.oss import get_cross_building_settings
from conans.errors import ConanException
from conans.util.env_reader import get_env
from conans.util.log import logger


verbose_definition_name = "CMAKE_VERBOSE_MAKEFILE"
cmake_install_prefix_var_name = "CMAKE_INSTALL_PREFIX"
runtime_definition_var_name = "CONAN_LINK_RUNTIME"
cmake_in_local_cache_var_name = "CONAN_IN_LOCAL_CACHE"


def get_toolset(settings):
    if settings.get_safe("compiler") == "Visual Studio":
        subs_toolset = settings.get_safe("compiler.toolset")
        if subs_toolset:
            return subs_toolset
    return None


def get_generator(settings):
    if "CONAN_CMAKE_GENERATOR" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR"]

    compiler = settings.get_safe("compiler")
    arch = settings.get_safe("arch")
    compiler_version = settings.get_safe("compiler.version")
    os_build, _, _, _ = get_cross_building_settings(settings)

    if not compiler or not compiler_version or not arch:
        if os_build == "Windows":
            # Not enough settings to set a generator in Windows
            return None
        return "Unix Makefiles"

    if compiler == "Visual Studio":
        _visuals = {'8': '8 2005',
                    '9': '9 2008',
                    '10': '10 2010',
                    '11': '11 2012',
                    '12': '12 2013',
                    '14': '14 2015',
                    '15': '15 2017'}
        base = "Visual Studio %s" % _visuals.get(compiler_version,
                                                 "UnknownVersion %s" % compiler_version)
        if arch == "x86_64":
            return base + " Win64"
        elif "arm" in arch:
            return base + " ARM"
        else:
            return base

    # The generator depends on the build machine, not the target
    if os_build == "Windows":
        return "MinGW Makefiles"  # it is valid only under Windows

    return "Unix Makefiles"


def add_cmake_flag(cmake_flags, name, flag):
    """
    appends compiler linker flags (if already present), or just sets
    """
    if flag:
        if name not in cmake_flags:
            cmake_flags[name] = flag
        else:
            cmake_flags[name] = ' ' + flag
    return cmake_flags


def is_multi_configuration(generator):
    return "Visual" in generator or "Xcode" in generator


def verbose_definition(value):
    return {verbose_definition_name: "ON" if value else "OFF"}


def in_local_cache_definition(value):
    return {cmake_in_local_cache_var_name: "ON" if value else "OFF"}


def runtime_definition(runtime):
    return {runtime_definition_var_name: "/%s" % runtime} if runtime else {}


def build_type_definition(build_type, generator):
    if build_type and not is_multi_configuration(generator):
        return {"CMAKE_BUILD_TYPE": build_type}
    return {}


class CMakeDefinitionsBuilder(object):

    def __init__(self, conanfile, cmake_system_name=True, make_program=None,
                 parallel=True, generator=None, set_cmake_flags=False):
        self._conanfile = conanfile
        self._forced_cmake_system_name = cmake_system_name
        self._make_program = make_program
        self._parallel = parallel
        self._forced_generator = generator
        self._set_cmake_flags = set_cmake_flags

    @property
    def generator(self):
        return self._forced_generator or get_generator(self._conanfile.settings)

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _get_cpp_standard_vars(self):
        cppstd = self._ss("cppstd")
        compiler = self._ss("compiler")
        compiler_version = self._ss("compiler.version")

        if not cppstd:
            return {}

        ret = {}
        if cppstd.startswith("gnu"):
            ret["CONAN_CMAKE_CXX_STANDARD"] = cppstd[3:]
            ret["CONAN_CMAKE_CXX_EXTENSIONS"] = "ON"
        else:
            ret["CONAN_CMAKE_CXX_STANDARD"] = cppstd
            ret["CONAN_CMAKE_CXX_EXTENSIONS"] = "OFF"

        ret["CONAN_STD_CXX_FLAG"] = cppstd_flag(compiler, compiler_version, cppstd)
        return ret

    def _cmake_cross_build_defines(self):

        os_ = self._ss("os")
        arch = self._ss("arch")
        os_ver_str = "os.api_level" if os_ == "Android" else "os.version"
        op_system_version = self._ss(os_ver_str)

        env_sn = get_env("CONAN_CMAKE_SYSTEM_NAME", "")
        env_sn = {"False": False, "True": True, "": None}.get(env_sn, env_sn)
        cmake_system_name = env_sn or self._forced_cmake_system_name

        os_build, _, _, _ = get_cross_building_settings(self._conanfile.settings)

        ret = OrderedDict()
        os_ver = get_env("CONAN_CMAKE_SYSTEM_VERSION", op_system_version)
        toolchain_file = get_env("CONAN_CMAKE_TOOLCHAIN_FILE", "")

        if toolchain_file != "":
            logger.info("Setting Cross build toolchain file: %s" % toolchain_file)
            ret["CMAKE_TOOLCHAIN_FILE"] = toolchain_file
            return ret

        if cmake_system_name is False:
            return ret

        # System name and system version
        if cmake_system_name is not True:  # String not empty
            ret["CMAKE_SYSTEM_NAME"] = cmake_system_name
        else:  # detect if we are cross building and the system name and version
            if cross_building(self._conanfile.settings):  # We are cross building
                if os_ != os_build:
                    if os_:  # the_os is the host (regular setting)
                        ret["CMAKE_SYSTEM_NAME"] = "Darwin" if os_ in ["iOS", "tvOS", "watchOS"] else os_
                    else:
                        ret["CMAKE_SYSTEM_NAME"] = "Generic"
        if os_ver:
            ret["CMAKE_SYSTEM_VERSION"] = os_ver

        # system processor
        cmake_system_processor = os.getenv("CONAN_CMAKE_SYSTEM_PROCESSOR")
        if cmake_system_processor:
            ret["CMAKE_SYSTEM_PROCESSOR"] = cmake_system_processor

        if ret:  # If enabled cross compile
            for env_var in ["CONAN_CMAKE_FIND_ROOT_PATH",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE"]:

                value = os.getenv(env_var)
                if value:
                    ret[env_var] = value

            if self._conanfile and self._conanfile.deps_cpp_info.sysroot:
                sysroot_path = self._conanfile.deps_cpp_info.sysroot
            else:
                sysroot_path = os.getenv("CONAN_CMAKE_FIND_ROOT_PATH", None)

            if sysroot_path:
                # Needs to be set here, can't be managed in the cmake generator, CMake needs
                # to know about the sysroot before any other thing
                ret["CMAKE_SYSROOT"] = sysroot_path.replace("\\", "/")

            # Adjust Android stuff
            if os_ == "Android":
                arch_abi_settings = {"armv8": "arm64-v8a",
                                     "armv7": "armeabi-v7a",
                                     "armv7hf": "armeabi-v7a",
                                     "armv6": "armeabi-v6",
                                     "armv5": "armeabi"
                                     }.get(arch, arch)
                if arch_abi_settings:
                    ret["CMAKE_ANDROID_ARCH_ABI"] = arch_abi_settings

        logger.info("Setting Cross build flags: %s"
                    % ", ".join(["%s=%s" % (k, v) for k, v in ret.items()]))
        return ret

    def _get_make_program_definition(self):
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or self._make_program
        if make_program:
            if not tools.which(make_program):
                self._conanfile.output.warn("The specified make program '%s' cannot be found"
                                            "and will be ignored" % make_program)
            else:
                self._conanfile.output.info("Using '%s' as CMAKE_MAKE_PROGRAM" % make_program)
                return {"CMAKE_MAKE_PROGRAM": make_program}

        return {}

    def get_definitions(self):

        compiler = self._ss("compiler")
        compiler_version = self._ss("compiler.version")
        arch = self._ss("arch")
        os_ = self._ss("os")
        libcxx = self._ss("compiler.libcxx")
        runtime = self._ss("compiler.runtime")
        build_type = self._ss("build_type")

        ret = OrderedDict()
        ret.update(build_type_definition(build_type, self.generator))
        ret.update(runtime_definition(runtime))

        if str(os_).lower() == "macos":
            if arch == "x86":
                ret["CMAKE_OSX_ARCHITECTURES"] = "i386"

        ret.update(self._cmake_cross_build_defines())
        ret.update(self._get_cpp_standard_vars())

        ret["CONAN_EXPORTED"] = "1"
        ret[cmake_in_local_cache_var_name] =\
            in_local_cache_definition(self._conanfile.in_local_cache)[cmake_in_local_cache_var_name]

        if compiler:
            ret["CONAN_COMPILER"] = compiler
        if compiler_version:
            ret["CONAN_COMPILER_VERSION"] = str(compiler_version)

        # Force compiler flags -- TODO: give as environment/setting parameter?
        arch_flag = architecture_flag(compiler=compiler, arch=arch)
        ret = add_cmake_flag(ret, 'CONAN_CXX_FLAGS', arch_flag)
        ret = add_cmake_flag(ret, 'CONAN_SHARED_LINKER_FLAGS', arch_flag)
        ret = add_cmake_flag(ret, 'CONAN_C_FLAGS', arch_flag)

        if libcxx:
            ret["CONAN_LIBCXX"] = libcxx

        # Shared library
        try:
            ret["BUILD_SHARED_LIBS"] = "ON" if self._conanfile.options.shared else "OFF"
        except ConanException:
            pass

        # Install to package folder
        try:
            if self._conanfile.package_folder:
                ret["CMAKE_INSTALL_PREFIX"] = self._conanfile.package_folder
        except AttributeError:
            pass

        if str(os_) in ["Windows", "WindowsStore"] and compiler == "Visual Studio":
            if self._parallel:
                flag = parallel_compiler_cl_flag()
                ret = add_cmake_flag(ret, 'CONAN_CXX_FLAGS', flag)
                ret = add_cmake_flag(ret, 'CONAN_C_FLAGS', flag)

        # fpic
        if str(os_) not in ["Windows", "WindowsStore"]:
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                ret["CONAN_CMAKE_POSITION_INDEPENDENT_CODE"] = "ON" if (fpic or shared) else "OFF"

        # Adjust automatically the module path in case the conanfile is using the cmake_find_package
        if "cmake_find_package" in self._conanfile.generators:
            ret["CMAKE_MODULE_PATH"] = self._conanfile.install_folder.replace("\\", "/")

        ret.update(self._get_make_program_definition())

        if self._set_cmake_flags:
            ret = add_cmake_flag(ret, 'CMAKE_CXX_FLAGS', arch_flag)
            ret = add_cmake_flag(ret, 'CMAKE_SHARED_LINKER_FLAGS', arch_flag)
            ret = add_cmake_flag(ret, 'CMAKE_C_FLAGS', arch_flag)

        # Disable CMake export registry #3070 (CMake installing modules in user home's)
        ret["CMAKE_EXPORT_NO_PACKAGE_REGISTRY"] = "ON"

        return ret
