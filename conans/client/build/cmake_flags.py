import os
import platform
from collections import OrderedDict

from conans.client import tools
from conans.client.build.compiler_flags import architecture_flag, parallel_compiler_cl_flag
from conans.client.build.cppstd_flags import cppstd_from_settings, cppstd_flag_new as cppstd_flag
from conans.client.tools import cross_building, Version
from conans.client.tools.apple import is_apple_os
from conans.client.tools.oss import get_cross_building_settings
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_SHARE
from conans.util.env_reader import get_env
from conans.util.log import logger

verbose_definition_name = "CMAKE_VERBOSE_MAKEFILE"
cmake_install_prefix_var_name = "CMAKE_INSTALL_PREFIX"
runtime_definition_var_name = "CONAN_LINK_RUNTIME"
cmake_in_local_cache_var_name = "CONAN_IN_LOCAL_CACHE"


def get_toolset(settings, generator):
    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    if compiler == "Visual Studio":
        subs_toolset = settings.get_safe("compiler.toolset")
        if subs_toolset:
            return subs_toolset
    elif compiler == "intel" and compiler_base == "Visual Studio" and "Visual" in generator:
        compiler_version = settings.get_safe("compiler.version")
        if compiler_version:
            compiler_version = compiler_version if "." in compiler_version else \
                "%s.0" % compiler_version
            return "Intel C++ Compiler " + compiler_version
    return None


def get_generator(conanfile):
    # Returns the name of the generator to be used by CMake
    if "CONAN_CMAKE_GENERATOR" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR"]

    compiler = conanfile.settings.get_safe("compiler")
    compiler_base = conanfile.settings.get_safe("compiler.base")
    arch = conanfile.settings.get_safe("arch")
    compiler_version = conanfile.settings.get_safe("compiler.version")
    compiler_base_version = conanfile.settings.get_safe("compiler.base.version")
    os_build, _, _, _ = get_cross_building_settings(conanfile)

    if not compiler or not compiler_version or not arch:
        if os_build == "Windows":
            logger.warning("CMake generator could not be deduced from settings")
            return None
        return "Unix Makefiles"

    if compiler == "Visual Studio" or compiler_base == "Visual Studio":
        version = compiler_base_version or compiler_version
        _visuals = {'8': '8 2005',
                    '9': '9 2008',
                    '10': '10 2010',
                    '11': '11 2012',
                    '12': '12 2013',
                    '14': '14 2015',
                    '15': '15 2017',
                    '16': '16 2019'}.get(version, "UnknownVersion %s" % version)
        base = "Visual Studio %s" % _visuals
        return base

    # The generator depends on the build machine, not the target
    if os_build == "Windows" and compiler != "qcc":
        return "MinGW Makefiles"  # it is valid only under Windows

    return "Unix Makefiles"


def get_generator_platform(settings, generator):
    # Returns the generator platform to be used by CMake
    if "CONAN_CMAKE_GENERATOR_PLATFORM" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR_PLATFORM"]

    compiler = settings.get_safe("compiler")
    compiler_base = settings.get_safe("compiler.base")
    arch = settings.get_safe("arch")

    if settings.get_safe("os") == "WindowsCE":
        return settings.get_safe("os.platform")

    if (compiler == "Visual Studio" or compiler_base == "Visual Studio") and \
            generator and "Visual" in generator:
        return {"x86": "Win32",
                "x86_64": "x64",
                "armv7": "ARM",
                "armv8": "ARM64"}.get(arch)
    return None


def is_multi_configuration(generator):
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator


def is_toolset_supported(generator):
    # https://cmake.org/cmake/help/v3.14/variable/CMAKE_GENERATOR_TOOLSET.html
    if not generator:
        return False
    return "Visual" in generator or "Xcode" in generator or "Green Hills MULTI" in generator


def is_generator_platform_supported(generator):
    # https://cmake.org/cmake/help/v3.14/variable/CMAKE_GENERATOR_PLATFORM.html
    if not generator:
        return False
    return "Visual" in generator or "Green Hills MULTI" in generator


def verbose_definition(value):
    return {verbose_definition_name: "ON" if value else "OFF"}


def in_local_cache_definition(value):
    return {cmake_in_local_cache_var_name: "ON" if value else "OFF"}


def runtime_definition(runtime):
    return {runtime_definition_var_name: "/%s" % runtime} if runtime else {}


def build_type_definition(new_build_type, old_build_type, generator, output):
    if new_build_type and new_build_type != old_build_type:
        output.warn("Forced CMake build type ('%s') different from the settings build type ('%s')"
                    % (new_build_type, old_build_type))

    build_type = new_build_type or old_build_type
    if build_type and not is_multi_configuration(generator):
        return {"CMAKE_BUILD_TYPE": build_type}
    return {}


class CMakeDefinitionsBuilder(object):

    def __init__(self, conanfile, cmake_system_name=True, make_program=None,
                 parallel=True, generator=None, set_cmake_flags=False,
                 forced_build_type=None, output=None):
        self._conanfile = conanfile
        self._forced_cmake_system_name = cmake_system_name
        self._make_program = make_program
        self._parallel = parallel
        self._generator = generator
        self._set_cmake_flags = set_cmake_flags
        self._forced_build_type = forced_build_type
        self._output = output

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _get_cpp_standard_vars(self):
        cppstd = cppstd_from_settings(self._conanfile.settings)

        if not cppstd:
            return {}

        definitions = {}
        if cppstd.startswith("gnu"):
            definitions["CONAN_CMAKE_CXX_STANDARD"] = cppstd[3:]
            definitions["CONAN_CMAKE_CXX_EXTENSIONS"] = "ON"
        else:
            definitions["CONAN_CMAKE_CXX_STANDARD"] = cppstd
            definitions["CONAN_CMAKE_CXX_EXTENSIONS"] = "OFF"

        definitions["CONAN_STD_CXX_FLAG"] = cppstd_flag(self._conanfile.settings)
        return definitions

    def _cmake_cross_build_defines(self, cmake_version):
        os_ = self._ss("os")
        arch = self._ss("arch")
        os_ver_str = "os.api_level" if os_ == "Android" else "os.version"
        op_system_version = self._ss(os_ver_str)

        env_sn = get_env("CONAN_CMAKE_SYSTEM_NAME", "")
        env_sn = {"False": False, "True": True, "": None}.get(env_sn, env_sn)
        cmake_system_name = env_sn or self._forced_cmake_system_name

        os_build, _, _, _ = get_cross_building_settings(self._conanfile)
        compiler = self._ss("compiler")
        libcxx = self._ss("compiler.libcxx")

        definitions = OrderedDict()
        os_ver = get_env("CONAN_CMAKE_SYSTEM_VERSION", op_system_version)
        toolchain_file = get_env("CONAN_CMAKE_TOOLCHAIN_FILE", "")

        if toolchain_file != "":
            logger.info("Setting Cross build toolchain file: %s" % toolchain_file)
            definitions["CMAKE_TOOLCHAIN_FILE"] = toolchain_file
            return definitions

        if cmake_system_name is False:
            return definitions

        # System name and system version
        if cmake_system_name is not True:  # String not empty
            definitions["CMAKE_SYSTEM_NAME"] = cmake_system_name
        else:  # detect if we are cross building and the system name and version
            skip_x64_x86 = os_ in ['Windows', 'Linux', 'SunOS', 'AIX']
            if cross_building(self._conanfile, skip_x64_x86=skip_x64_x86):  # We are cross building
                apple_system_name = "Darwin" if cmake_version and Version(cmake_version) < Version(
                    "3.14") or not cmake_version else None
                cmake_system_name_map = {"Macos": "Darwin",
                                         "iOS": apple_system_name or "iOS",
                                         "tvOS": apple_system_name or "tvOS",
                                         "watchOS": apple_system_name or "watchOS",
                                         "Neutrino": "QNX",
                                         "": "Generic",
                                         None: "Generic"}
                definitions["CMAKE_SYSTEM_NAME"] = cmake_system_name_map.get(os_, os_)

        if os_ver:
            definitions["CMAKE_SYSTEM_VERSION"] = os_ver
            if is_apple_os(os_):
                definitions["CMAKE_OSX_DEPLOYMENT_TARGET"] = os_ver

        # system processor
        cmake_system_processor = os.getenv("CONAN_CMAKE_SYSTEM_PROCESSOR")
        if cmake_system_processor:
            definitions["CMAKE_SYSTEM_PROCESSOR"] = cmake_system_processor

        if definitions:  # If enabled cross compile
            for env_var in ["CONAN_CMAKE_FIND_ROOT_PATH",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE"]:

                value = os.getenv(env_var)
                if value:
                    definitions[env_var] = value

            if self._conanfile and self._conanfile.deps_cpp_info.sysroot:
                sysroot_path = self._conanfile.deps_cpp_info.sysroot
            else:
                sysroot_path = os.getenv("CONAN_CMAKE_FIND_ROOT_PATH", None)

            if sysroot_path:
                # Needs to be set here, can't be managed in the cmake generator, CMake needs
                # to know about the sysroot before any other thing
                definitions["CMAKE_SYSROOT"] = sysroot_path.replace("\\", "/")

            # Adjust Android stuff
            if str(os_) == "Android" and definitions["CMAKE_SYSTEM_NAME"] == "Android":
                arch_abi_settings = tools.to_android_abi(arch)
                if arch_abi_settings:
                    definitions["CMAKE_ANDROID_ARCH_ABI"] = arch_abi_settings
                    definitions["ANDROID_ABI"] = arch_abi_settings

                conan_cmake_android_ndk = os.getenv("CONAN_CMAKE_ANDROID_NDK")
                if conan_cmake_android_ndk:
                    definitions["ANDROID_NDK"] = conan_cmake_android_ndk

                definitions["ANDROID_PLATFORM"] = "android-%s" % op_system_version
                definitions["ANDROID_TOOLCHAIN"] = compiler

                # More details about supported stdc++ libraries here:
                # https://developer.android.com/ndk/guides/cpp-support.html
                if libcxx:
                    definitions["ANDROID_STL"] = libcxx
                else:
                    definitions["ANDROID_STL"] = 'none'

        logger.info("Setting Cross build flags: %s"
                    % ", ".join(["%s=%s" % (k, v) for k, v in definitions.items()]))
        return definitions

    def _get_make_program_definition(self):
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or self._make_program
        if make_program:
            if not tools.which(make_program):
                self._output.warn("The specified make program '%s' cannot be found and will be "
                                  "ignored" % make_program)
            else:
                self._output.info("Using '%s' as CMAKE_MAKE_PROGRAM" % make_program)
                return {"CMAKE_MAKE_PROGRAM": make_program}

        return {}

    def get_definitions(self, cmake_version):

        compiler = self._ss("compiler")
        compiler_base = self._ss("compiler.base")
        compiler_version = self._ss("compiler.version")
        arch = self._ss("arch")
        os_ = self._ss("os")
        libcxx = self._ss("compiler.libcxx")
        runtime = self._ss("compiler.runtime")
        build_type = self._ss("build_type")

        definitions = OrderedDict()
        definitions.update(runtime_definition(runtime))
        definitions.update(build_type_definition(self._forced_build_type, build_type,
                                                 self._generator, self._output))

        # don't attempt to override variables set within toolchain
        if (tools.is_apple_os(os_) and "CONAN_CMAKE_TOOLCHAIN_FILE" not in os.environ
                and "CMAKE_TOOLCHAIN_FILE" not in definitions):
            apple_arch = tools.to_apple_arch(arch)
            if apple_arch:
                definitions["CMAKE_OSX_ARCHITECTURES"] = apple_arch
            # xcrun is only available on macOS, otherwise it's cross-compiling and it needs to be
            # set within CMake toolchain. also, if SDKROOT is set, CMake will use it, and it's not
            # needed to run xcrun.
            if platform.system() == "Darwin" and "SDKROOT" not in os.environ:
                sdk_path = tools.XCRun(self._conanfile.settings).sdk_path
                if sdk_path:
                    definitions["CMAKE_OSX_SYSROOT"] = sdk_path

        definitions.update(self._cmake_cross_build_defines(cmake_version))
        definitions.update(self._get_cpp_standard_vars())

        definitions.update(in_local_cache_definition(self._conanfile.in_local_cache))

        if compiler:
            definitions["CONAN_COMPILER"] = compiler
        if compiler_version:
            definitions["CONAN_COMPILER_VERSION"] = str(compiler_version)

        # C, CXX, LINK FLAGS
        if compiler == "Visual Studio" or compiler_base == "Visual Studio":
            if self._parallel:
                flag = parallel_compiler_cl_flag(output=self._output)
                definitions['CONAN_CXX_FLAGS'] = flag
                definitions['CONAN_C_FLAGS'] = flag
        else:  # arch_flag is only set for non Visual Studio
            arch_flag = architecture_flag(self._conanfile.settings)
            if arch_flag:
                definitions['CONAN_CXX_FLAGS'] = arch_flag
                definitions['CONAN_SHARED_LINKER_FLAGS'] = arch_flag
                definitions['CONAN_C_FLAGS'] = arch_flag
                if self._set_cmake_flags:
                    definitions['CMAKE_CXX_FLAGS'] = arch_flag
                    definitions['CMAKE_SHARED_LINKER_FLAGS'] = arch_flag
                    definitions['CMAKE_C_FLAGS'] = arch_flag

        if libcxx:
            definitions["CONAN_LIBCXX"] = libcxx

        # Shared library
        try:
            definitions["BUILD_SHARED_LIBS"] = "ON" if self._conanfile.options.shared else "OFF"
        except ConanException:
            pass

        # Install to package folder
        try:
            if self._conanfile.package_folder:
                definitions["CMAKE_INSTALL_PREFIX"] = self._conanfile.package_folder
                definitions["CMAKE_INSTALL_BINDIR"] = DEFAULT_BIN
                definitions["CMAKE_INSTALL_SBINDIR"] = DEFAULT_BIN
                definitions["CMAKE_INSTALL_LIBEXECDIR"] = DEFAULT_BIN
                definitions["CMAKE_INSTALL_LIBDIR"] = DEFAULT_LIB
                definitions["CMAKE_INSTALL_INCLUDEDIR"] = DEFAULT_INCLUDE
                definitions["CMAKE_INSTALL_OLDINCLUDEDIR"] = DEFAULT_INCLUDE
                definitions["CMAKE_INSTALL_DATAROOTDIR"] = DEFAULT_SHARE
        except AttributeError:
            pass

        # fpic
        if not str(os_).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                fpic_value = "ON" if (fpic or shared) else "OFF"
                definitions["CONAN_CMAKE_POSITION_INDEPENDENT_CODE"] = fpic_value

        # Adjust automatically the module path in case the conanfile is using the
        # cmake_find_package or cmake_find_package_multi
        install_folder = self._conanfile.install_folder.replace("\\", "/")
        if "cmake_find_package" in self._conanfile.generators:
            definitions["CMAKE_MODULE_PATH"] = install_folder

        if "cmake_find_package_multi" in self._conanfile.generators:
            # The cmake_find_package_multi only works with targets and generates XXXConfig.cmake
            # that require the prefix path and the module path
            definitions["CMAKE_PREFIX_PATH"] = install_folder
            definitions["CMAKE_MODULE_PATH"] = install_folder

        definitions.update(self._get_make_program_definition())

        # Disable CMake export registry #3070 (CMake installing modules in user home's)
        definitions["CMAKE_EXPORT_NO_PACKAGE_REGISTRY"] = "ON"
        return definitions
