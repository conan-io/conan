import os
from collections import OrderedDict

from conans.client import tools
from conans.client.build.compiler_flags import architecture_flag, parallel_compiler_cl_flag
from conans.client.build.cppstd_flags import cppstd_flag, cppstd_from_settings
from conans.client.tools import cross_building
from conans.client.tools.oss import get_cross_building_settings
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB, DEFAULT_SHARE
from conans.model.version import Version
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
    os_host = settings.get_safe("os")

    if not compiler or not compiler_version or not arch:
        if os_build == "Windows":
            logger.warning("CMake generator could not be deduced from settings")
            return None
        return "Unix Makefiles"

    if compiler == "Visual Studio":
        _visuals = {'8': '8 2005',
                    '9': '9 2008',
                    '10': '10 2010',
                    '11': '11 2012',
                    '12': '12 2013',
                    '14': '14 2015',
                    '15': '15 2017',
                    '16': '16 2019'}
        base = "Visual Studio %s" % _visuals.get(compiler_version,
                                                 "UnknownVersion %s" % compiler_version)
        if os_host != "WindowsCE" and Version(compiler_version) < "16":
            if arch == "x86_64":
                base += " Win64"
            elif "arm" in arch:
                base += " ARM"
        return base

    # The generator depends on the build machine, not the target
    if os_build == "Windows" and compiler != "qcc":
        return "MinGW Makefiles"  # it is valid only under Windows

    return "Unix Makefiles"


def get_generator_platform(settings, generator):
    if "CONAN_CMAKE_GENERATOR_PLATFORM" in os.environ:
        return os.environ["CONAN_CMAKE_GENERATOR_PLATFORM"]

    compiler = settings.get_safe("compiler")
    arch = settings.get_safe("arch")
    compiler_version = settings.get_safe("compiler.version")

    if settings.get_safe("os") == "WindowsCE":
        return settings.get_safe("os.platform")

    if compiler == "Visual Studio" and Version(compiler_version) >= "16" \
            and "Visual" in generator:
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


def build_type_definition(build_type, generator):
    if build_type and not is_multi_configuration(generator):
        return {"CMAKE_BUILD_TYPE": build_type}
    return {}


class CMakeDefinitions(object):

    def __init__(self, definitions=None):
        if definitions:
            assert isinstance(definitions, dict), "definitions is not an dict"
        self._definitions = definitions or OrderedDict()

    def set(self, key, value):
        self._set(key, value)

    def _set(self, key, value, new=False):
        if not new:
            assert key in self._definitions, "key not previously set in dictionary"
            assert self._definitions[key] is None, "key already has a value assigned"
        else:
            assert key not in self._definitions, "key previously set in dictionary"
        self._definitions[key] = value

    def update(self, definitions):
        for key, value in definitions.items():
            self._set(key, value, True)

    def get(self, key, value=None):
        assert key in self._definitions, "key not previously set in dictionary"
        return self._definitions.get(key, value)

    def result(self):
        return OrderedDict({key: value for key, value in self._definitions.items() if value})


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
        defines = CMakeDefinitions({
            "CONAN_CMAKE_CXX_STANDARD": None,
            "CONAN_CMAKE_CXX_EXTENSIONS": None,
            "CONAN_STD_CXX_FLAG": None})

        cppstd = cppstd_from_settings(self._conanfile.settings)
        compiler = self._ss("compiler")
        compiler_version = self._ss("compiler.version")

        if not cppstd:
            return defines.result()

        if cppstd.startswith("gnu"):
            defines.set("CONAN_CMAKE_CXX_STANDARD", cppstd[3:])
            defines.set("CONAN_CMAKE_CXX_EXTENSIONS", "ON")
        else:
            defines.set("CONAN_CMAKE_CXX_STANDARD", cppstd)
            defines.set("CONAN_CMAKE_CXX_EXTENSIONS", "OFF")

        defines.set("CONAN_STD_CXX_FLAG", cppstd_flag(compiler, compiler_version, cppstd))
        return defines.result()

    def _cmake_cross_build_defines(self):

        os_ = self._ss("os")
        arch = self._ss("arch")
        os_ver_str = "os.api_level" if os_ == "Android" else "os.version"
        op_system_version = self._ss(os_ver_str)

        env_sn = get_env("CONAN_CMAKE_SYSTEM_NAME", "")
        env_sn = {"False": False, "True": True, "": None}.get(env_sn, env_sn)
        cmake_system_name = env_sn or self._forced_cmake_system_name

        os_build, _, _, _ = get_cross_building_settings(self._conanfile.settings)
        compiler = self._ss("compiler")
        libcxx = self._ss("compiler.libcxx")

        os_ver = get_env("CONAN_CMAKE_SYSTEM_VERSION", op_system_version)
        toolchain_file = get_env("CONAN_CMAKE_TOOLCHAIN_FILE", "")

        defines = CMakeDefinitions({
            "TOOLCHAIN_FILE": None,
            "CMAKE_SYSTEM_NAME": None,
            "CMAKE_SYSTEM_VERSION": None,
            "CMAKE_OSX_DEPLOYMENT_TARGET": None,
            "CMAKE_SYSTEM_PROCESSOR": None,
            "CONAN_CMAKE_FIND_ROOT_PATH": None,
            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM": None,
            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY": None,
            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE": None,
            "CMAKE_SYSROOT": None,
            "CMAKE_ANDROID_ARCH_ABI": None,
            "ANDROID_ABI": None,
            "ANDROID_NDK": None,
            "ANDROID_PLATFORM": None,
            "ANDROID_TOOLCHAIN": None,
            "ANDROID_STL": None
        })

        if toolchain_file != "":
            logger.info("Setting Cross build toolchain file: %s" % toolchain_file)
            defines.set("CMAKE_TOOLCHAIN_FILE", toolchain_file)

        if cmake_system_name is False:
            return defines.result()

        # System name and system version
        if cmake_system_name is not True:  # String not empty
            defines.set("CMAKE_SYSTEM_NAME", cmake_system_name)
        else:  # detect if we are cross building and the system name and version
            if cross_building(self._conanfile.settings):  # We are cross building
                if os_ != os_build:
                    if os_:  # the_os is the host (regular setting)
                        defines.set("CMAKE_SYSTEM_NAME", {"iOS": "Darwin",
                                                          "tvOS": "Darwin",
                                                          "watchOS": "Darwin",
                                                          "Neutrino": "QNX"}.get(os_, os_))
                    else:
                        defines.set("CMAKE_SYSTEM_NAME", "Generic")
        if os_ver:
            defines.set("CMAKE_SYSTEM_VERSION", os_ver)
            if str(os_) == "Macos":
                defines.set("CMAKE_OSX_DEPLOYMENT_TARGET", os_ver)

        # system processor
        cmake_system_processor = os.getenv("CONAN_CMAKE_SYSTEM_PROCESSOR")
        if cmake_system_processor:
            defines.set("CMAKE_SYSTEM_PROCESSOR", cmake_system_processor)

        if defines.result():
            for env_var in ["CONAN_CMAKE_FIND_ROOT_PATH",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY",
                            "CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE"]:

                value = os.getenv(env_var)
                if value:
                    defines.set(env_var, value)

            if self._conanfile and self._conanfile.deps_cpp_info.sysroot:
                sysroot_path = self._conanfile.deps_cpp_info.sysroot
            else:
                sysroot_path = os.getenv("CONAN_CMAKE_FIND_ROOT_PATH", None)

            if sysroot_path:
                # Needs to be set here, can't be managed in the cmake generator, CMake needs
                # to know about the sysroot before any other thing
                defines.set("CMAKE_SYSROOT", sysroot_path.replace("\\", "/"))

            # Adjust Android stuff
            if str(os_) == "Android" and defines.get("CMAKE_SYSTEM_NAME") == "Android":
                arch_abi_settings = tools.to_android_abi(arch)
                if arch_abi_settings:
                    defines.set("CMAKE_ANDROID_ARCH_ABI", arch_abi_settings)
                    defines.set("ANDROID_ABI", arch_abi_settings)

                conan_cmake_android_ndk = os.getenv("CONAN_CMAKE_ANDROID_NDK")
                if conan_cmake_android_ndk:
                    defines.set("ANDROID_NDK", conan_cmake_android_ndk)

                defines.set("ANDROID_PLATFORM", "android-%s" % op_system_version)
                defines.set("ANDROID_TOOLCHAIN", compiler)

                # More details about supported stdc++ libraries here:
                # https://developer.android.com/ndk/guides/cpp-support.html
                if libcxx:
                    defines.set("ANDROID_STL", libcxx)
                else:
                    defines.set("ANDROID_STL", "none")

        logger.info("Setting Cross build flags: %s"
                    % ", ".join(["%s=%s" % (k, v) for k, v in defines.result().items()]))

        return defines.result()

    def _get_make_program_definition(self):
        defines = CMakeDefinitions({"CMAKE_MAKE_PROGRAM": None})
        make_program = os.getenv("CONAN_MAKE_PROGRAM") or self._make_program
        if make_program:
            if not tools.which(make_program):
                self._output.warn("The specified make program '%s' cannot be found and will be "
                                  "ignored" % make_program)
            else:
                self._output.info("Using '%s' as CMAKE_MAKE_PROGRAM" % make_program)
                defines.set("CMAKE_MAKE_PROGRAM", make_program)
        return defines.result()

    def get_definitions(self):

        compiler = self._ss("compiler")
        compiler_version = self._ss("compiler.version")
        arch = self._ss("arch")
        os_ = self._ss("os")
        libcxx = self._ss("compiler.libcxx")
        runtime = self._ss("compiler.runtime")
        build_type = self._ss("build_type")

        defines = CMakeDefinitions({
            "CONAN_EXPORTED": "1",
            "CMAKE_OSX_ARCHITECTURES": None,
            "CONAN_COMPILER": None,
            "CONAN_COMPILER_VERSION": None,
            "CONAN_CXX_FLAGS": None,
            "CONAN_C_FLAGS": None,
            "CONAN_SHARED_LINKER_FLAGS": None,
            "CMAKE_C_FLAGS": None,
            "CMAKE_CXX_FLAGS": None,
            "CMAKE_SHARED_LINKER_FLAGS": None,
            "CONAN_LIBCXX": None,
            "BUILD_SHARED_LIBS": None,
            "CMAKE_INSTALL_PREFIX": None,
            "CMAKE_INSTALL_BINDIR": None,
            "CMAKE_INSTALL_SBINDIR": None,
            "CMAKE_INSTALL_LIBEXECDIR": None,
            "CMAKE_INSTALL_LIBDIR": None,
            "CMAKE_INSTALL_INCLUDEDIR": None,
            "CMAKE_INSTALL_OLDINCLUDEDIR": None,
            "CMAKE_INSTALL_DATAROOTDIR": None,
            "CONAN_CMAKE_POSITION_INDEPENDENT_CODE": None,
            "CMAKE_MODULE_PATH": None,
            "CMAKE_PREFIX_PATH": None,
            # Disable CMake export registry #3070 (CMake installing modules in user home's)
            "CMAKE_EXPORT_NO_PACKAGE_REGISTRY": "ON"
        })

        if self._forced_build_type and self._forced_build_type != build_type:
            self._output.warn("Forced CMake build type ('%s') different from the settings build "
                              "type ('%s')" % (self._forced_build_type, build_type))
            build_type = self._forced_build_type

        if str(os_) == "Macos":
            if arch == "x86":
                defines.set("CMAKE_OSX_ARCHITECTURES", "i386")

        if compiler:
            defines.set("CONAN_COMPILER", compiler)
        if compiler_version:
            defines.set("CONAN_COMPILER_VERSION", str(compiler_version))

        # C, CXX, LINK FLAGS
        if compiler == "Visual Studio":
            if self._parallel:
                flag = parallel_compiler_cl_flag(output=self._output)
                defines.set("CONAN_CXX_FLAGS", flag)
                defines.set("CONAN_C_FLAGS", flag)
        else:  # arch_flag is only set for non Visual Studio
            arch_flag = architecture_flag(compiler=compiler, os=os_, arch=arch)
            if arch_flag:
                defines.set("CONAN_CXX_FLAGS", arch_flag)
                defines.set("CONAN_SHARED_LINKER_FLAGS", arch_flag)
                defines.set("CONAN_C_FLAGS", arch_flag)
                if self._set_cmake_flags:
                    defines.set("CMAKE_CXX_FLAGS", arch_flag)
                    defines.set("CMAKE_SHARED_LINKER_FLAGS", arch_flag)
                    defines.set("CMAKE_C_FLAGS", arch_flag)

        if libcxx:
            defines.set("CONAN_LIBCXX", libcxx)

        # Shared library
        try:
            defines.set("BUILD_SHARED_LIBS", "ON" if self._conanfile.options.shared else "OFF")
        except ConanException:
            pass

        # Install to package folder
        try:
            if self._conanfile.package_folder:
                defines.set("CMAKE_INSTALL_PREFIX", self._conanfile.package_folder)
                defines.set("CMAKE_INSTALL_BINDIR", DEFAULT_BIN)
                defines.set("CMAKE_INSTALL_SBINDIR", DEFAULT_BIN)
                defines.set("CMAKE_INSTALL_LIBEXECDIR", DEFAULT_BIN)
                defines.set("CMAKE_INSTALL_LIBDIR", DEFAULT_LIB)
                defines.set("CMAKE_INSTALL_INCLUDEDIR", DEFAULT_INCLUDE)
                defines.set("CMAKE_INSTALL_OLDINCLUDEDIR", DEFAULT_INCLUDE)
                defines.set("CMAKE_INSTALL_DATAROOTDIR", DEFAULT_SHARE)
        except AttributeError:
            pass

        # fpic
        if not str(os_).startswith("Windows"):
            fpic = self._conanfile.options.get_safe("fPIC")
            if fpic is not None:
                shared = self._conanfile.options.get_safe("shared")
                defines.set("CONAN_CMAKE_POSITION_INDEPENDENT_CODE",
                            "ON" if (fpic or shared) else "OFF")

        # Adjust automatically the module path in case the conanfile is using the
        # cmake_find_package or cmake_find_package_multi
        install_folder = self._conanfile.install_folder.replace("\\", "/")
        if "cmake_find_package" in self._conanfile.generators:
            defines.set("CMAKE_MODULE_PATH", install_folder)

        if "cmake_find_package_multi" in self._conanfile.generators:
            # The cmake_find_package_multi only works with targets and generates XXXConfig.cmake
            # that require the prefix path and the module path
            defines.set("CMAKE_PREFIX_PATH", install_folder)
            defines.set("CMAKE_MODULE_PATH", install_folder)

        defines.update(build_type_definition(build_type, self._generator))
        defines.update(self._cmake_cross_build_defines())
        defines.update(self._get_cpp_standard_vars())
        defines.update(in_local_cache_definition(self._conanfile.in_local_cache))
        defines.update(self._get_make_program_definition())
        defines.update(runtime_definition(runtime))
        return defines.result()
