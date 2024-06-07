import os
import re
import textwrap
from collections import OrderedDict

from jinja2 import Template

from conan.internal.internal_tools import universal_arch_separator, is_universal_arch
from conan.tools.apple.apple import get_apple_sdk_fullname, _to_apple_arch
from conan.tools.android.utils import android_abi
from conan.tools.apple.apple import is_apple_os, to_apple_arch
from conan.tools.build import build_jobs
from conan.tools.build.flags import architecture_flag, libcxx_flags
from conan.tools.build.cross_building import cross_building
from conan.tools.cmake.toolchain import CONAN_TOOLCHAIN_FILENAME
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.intel import IntelCC
from conan.tools.microsoft.visual import msvc_version_to_toolset_version
from conans.client.generators import relativize_path
from conans.client.subsystems import deduce_subsystem, WINDOWS
from conan.errors import ConanException
from conans.model.version import Version
from conans.util.files import load


class Block(object):
    def __init__(self, conanfile, toolchain):
        self._conanfile = conanfile
        self._toolchain = toolchain
        self._context_values = None

    @property
    def values(self):
        if self._context_values is None:
            self._context_values = self.context()
        return self._context_values

    @values.setter
    def values(self, context_values):
        self._context_values = context_values

    def get_rendered_content(self):
        context = self.values
        if context is None:
            return

        template = Template(self.template, trim_blocks=True, lstrip_blocks=True)
        return template.render(**context)

    def context(self):
        return {}

    @property
    def template(self):
        raise NotImplementedError()


class VSRuntimeBlock(Block):
    template = textwrap.dedent("""
        # Definition of VS runtime, defined from build_type, compiler.runtime, compiler.runtime_type
        {% set genexpr = namespace(str='') %}
        {% for config, value in vs_runtimes.items() %}
            {% set genexpr.str = genexpr.str +
                                  '$<$<CONFIG:' + config + '>:' + value|string + '>' %}
        {% endfor %}
        cmake_policy(GET CMP0091 POLICY_CMP0091)
        if(NOT "${POLICY_CMP0091}" STREQUAL NEW)
            message(FATAL_ERROR "The CMake policy CMP0091 must be NEW, but is '${POLICY_CMP0091}'")
        endif()
        set(CMAKE_MSVC_RUNTIME_LIBRARY "{{ genexpr.str }}")
        """)

    def context(self):
        # Parsing existing toolchain file to get existing configured runtimes
        settings = self._conanfile.settings
        if settings.get_safe("os") != "Windows":
            return

        compiler = settings.get_safe("compiler")
        if compiler not in ("msvc", "clang", "intel-cc"):
            return

        runtime = settings.get_safe("compiler.runtime")
        if runtime is None:
            return

        config_dict = {}
        if os.path.exists(CONAN_TOOLCHAIN_FILENAME):
            existing_include = load(CONAN_TOOLCHAIN_FILENAME)
            msvc_runtime_value = re.search(r"set\(CMAKE_MSVC_RUNTIME_LIBRARY \"([^)]*)\"\)",
                                           existing_include)
            if msvc_runtime_value:
                capture = msvc_runtime_value.group(1)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:([A-Za-z]*)>", capture)
                config_dict = dict(matches)

        build_type = settings.get_safe("build_type")  # FIXME: change for configuration
        if build_type is None:
            return None

        if compiler == "msvc" or compiler == "intel-cc" or compiler == "clang":
            runtime_type = settings.get_safe("compiler.runtime_type")
            rt = "MultiThreadedDebug" if runtime_type == "Debug" else "MultiThreaded"
            if runtime != "static":
                rt += "DLL"
            config_dict[build_type] = rt

            # If clang is being used the CMake check of compiler will try to create a simple
            # test application, and will fail because the Debug runtime is not there
            if compiler == "clang":
                if config_dict.get("Debug") is None:
                    clang_rt = "MultiThreadedDebug" + ("DLL" if runtime != "static" else "")
                    config_dict["Debug"] = clang_rt

        return {"vs_runtimes": config_dict}


class VSDebuggerEnvironment(Block):
    template = textwrap.dedent("""
        {% if vs_debugger_path %}
        # Definition of CMAKE_VS_DEBUGGER_ENVIRONMENT
        set(CMAKE_VS_DEBUGGER_ENVIRONMENT "{{ vs_debugger_path }}")
        {% endif %}
        """)

    def context(self):
        os_ = self._conanfile.settings.get_safe("os")
        build_type = self._conanfile.settings.get_safe("build_type")

        if (os_ and "Windows" not in os_) or not build_type:
            return None

        if "Visual" not in self._toolchain.generator:
            return None

        config_dict = {}
        if os.path.exists(CONAN_TOOLCHAIN_FILENAME):
            existing_include = load(CONAN_TOOLCHAIN_FILENAME)
            pattern = r"set\(CMAKE_VS_DEBUGGER_ENVIRONMENT \"PATH=([^)]*);%PATH%\"\)"
            vs_debugger_environment = re.search(pattern, existing_include)
            if vs_debugger_environment:
                capture = vs_debugger_environment.group(1)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:([^>]*)>", capture)
                config_dict = dict(matches)

        host_deps = self._conanfile.dependencies.host.values()
        test_deps = self._conanfile.dependencies.test.values()
        bin_dirs = [p for dep in host_deps for p in dep.cpp_info.aggregated_components().bindirs]
        test_bindirs = [p for dep in test_deps for p in dep.cpp_info.aggregated_components().bindirs]
        bin_dirs.extend(test_bindirs)
        bin_dirs = [relativize_path(p, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
                    for p in bin_dirs]
        bin_dirs = [p.replace("\\", "/") for p in bin_dirs]
        bin_dirs = ";".join(bin_dirs) if bin_dirs else None
        if bin_dirs:
            config_dict[build_type] = bin_dirs

        if not config_dict:
            return None

        vs_debugger_path = ""
        for config, value in config_dict.items():
            vs_debugger_path += f"$<$<CONFIG:{config}>:{value}>"
        vs_debugger_path = f"PATH={vs_debugger_path};%PATH%"
        return {"vs_debugger_path": vs_debugger_path}


class FPicBlock(Block):
    template = textwrap.dedent("""
        {% if fpic %}
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE={{ fpic }} (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE {{ fpic }} CACHE BOOL "Position independent code")
        {% endif %}
        """)

    def context(self):
        fpic = self._conanfile.options.get_safe("fPIC")
        if fpic is None:
            return None
        os_ = self._conanfile.settings.get_safe("os")
        if os_ and "Windows" in os_:
            self._conanfile.output.warning("Toolchain: Ignoring fPIC option defined for Windows")
            return None
        return {"fpic": "ON" if fpic else "OFF"}


class GLibCXXBlock(Block):
    template = textwrap.dedent("""
        {% if set_libcxx %}
        string(APPEND CONAN_CXX_FLAGS " {{ set_libcxx }}")
        {% endif %}
        {% if glibcxx %}
        add_compile_definitions({{ glibcxx }})
        {% endif %}
        """)

    def context(self):
        libcxx, stdlib11 = libcxx_flags(self._conanfile)
        return {"set_libcxx": libcxx, "glibcxx": stdlib11}


class SkipRPath(Block):
    template = textwrap.dedent("""
        {% if skip_rpath %}
        set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
        # Policy CMP0068
        # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect install_name in OSX
        set(CMAKE_INSTALL_NAME_DIR "")
        {% endif %}
        """)

    skip_rpath = False

    def context(self):
        return {"skip_rpath": self.skip_rpath}


class ArchitectureBlock(Block):
    template = textwrap.dedent("""
        string(APPEND CONAN_CXX_FLAGS " {{ arch_flag }}")
        string(APPEND CONAN_C_FLAGS " {{ arch_flag }}")
        string(APPEND CONAN_SHARED_LINKER_FLAGS " {{ arch_flag }}")
        string(APPEND CONAN_EXE_LINKER_FLAGS " {{ arch_flag }}")
        """)

    def context(self):
        arch_flag = architecture_flag(self._conanfile.settings)
        if not arch_flag:
            return
        return {"arch_flag": arch_flag}


class LinkerScriptsBlock(Block):
    template = textwrap.dedent("""
        string(APPEND CONAN_EXE_LINKER_FLAGS {{ linker_script_flags }})
        """)

    def context(self):
        linker_scripts = self._conanfile.conf.get(
            "tools.build:linker_scripts", check_type=list, default=[])
        if not linker_scripts:
            return
        linker_scripts = [linker_script.replace('\\', '/') for linker_script in linker_scripts]
        linker_scripts = [relativize_path(p, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
                          for p in linker_scripts]
        linker_script_flags = ['-T"' + linker_script + '"' for linker_script in linker_scripts]
        return {"linker_script_flags": " ".join(linker_script_flags)}


class CppStdBlock(Block):
    template = textwrap.dedent("""
        {% if cppstd %}
        message(STATUS "Conan toolchain: C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
        set(CMAKE_CXX_STANDARD_REQUIRED ON)
        {% endif %}
        {% if cstd %}
        message(STATUS "Conan toolchain: C Standard {{ cstd }} with extensions {{ cstd_extensions }}")
        set(CMAKE_C_STANDARD {{ cstd }})
        set(CMAKE_C_EXTENSIONS {{ cstd_extensions }})
        set(CMAKE_C_STANDARD_REQUIRED ON)
        {% endif %}
        """)

    def context(self):
        compiler_cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        compiler_cstd = self._conanfile.settings.get_safe("compiler.cstd")
        result = {}
        if compiler_cppstd is not None:
            if compiler_cppstd.startswith("gnu"):
                result["cppstd"] = compiler_cppstd[3:]
                result["cppstd_extensions"] = "ON"
            else:
                result["cppstd"] = compiler_cppstd
                result["cppstd_extensions"] = "OFF"
        if compiler_cstd is not None:
            if compiler_cstd.startswith("gnu"):
                result["cstd"] = compiler_cstd[3:]
                result["cstd_extensions"] = "ON"
            else:
                result["cstd"] = compiler_cstd
                result["cstd_extensions"] = "OFF"
        return result or None


class SharedLibBock(Block):
    template = textwrap.dedent("""
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS = {{ shared_libs }}")
        set(BUILD_SHARED_LIBS {{ shared_libs }} CACHE BOOL "Build shared libraries")
        """)

    def context(self):
        try:
            shared_libs = "ON" if self._conanfile.options.shared else "OFF"
            return {"shared_libs": shared_libs}
        except ConanException:
            return None


class ParallelBlock(Block):
    template = textwrap.dedent("""
        string(APPEND CONAN_CXX_FLAGS " /MP{{ parallel }}")
        string(APPEND CONAN_C_FLAGS " /MP{{ parallel }}")
        """)

    def context(self):
        # TODO: Check this conf

        compiler = self._conanfile.settings.get_safe("compiler")
        if compiler != "msvc" or "Visual" not in self._toolchain.generator:
            return

        jobs = build_jobs(self._conanfile)
        if jobs:
            return {"parallel": jobs}


class AndroidSystemBlock(Block):

    template = textwrap.dedent("""
        # New toolchain things
        set(ANDROID_PLATFORM {{ android_platform }})
        {% if android_stl %}
        set(ANDROID_STL {{ android_stl }})
        {% endif %}
        set(ANDROID_ABI {{ android_abi }})
        {% if android_use_legacy_toolchain_file %}
        set(ANDROID_USE_LEGACY_TOOLCHAIN_FILE {{ android_use_legacy_toolchain_file }})
        {% endif %}
        include({{ android_ndk_path }}/build/cmake/android.toolchain.cmake)
        """)

    def context(self):
        os_ = self._conanfile.settings.get_safe("os")
        if os_ != "Android":
            return

        # TODO: only 'c++_shared' y 'c++_static' supported?
        #  https://developer.android.com/ndk/guides/cpp-support
        libcxx_str = self._conanfile.settings.get_safe("compiler.libcxx")

        android_ndk_path = self._conanfile.conf.get("tools.android:ndk_path")
        if not android_ndk_path:
            raise ConanException('CMakeToolchain needs tools.android:ndk_path configuration defined')
        android_ndk_path = android_ndk_path.replace("\\", "/")
        android_ndk_path = relativize_path(android_ndk_path, self._conanfile,
                                           "${CMAKE_CURRENT_LIST_DIR}")

        use_cmake_legacy_toolchain = self._conanfile.conf.get("tools.android:cmake_legacy_toolchain",
                                                              check_type=bool)
        if use_cmake_legacy_toolchain is not None:
            use_cmake_legacy_toolchain = "ON" if use_cmake_legacy_toolchain else "OFF"

        ctxt_toolchain = {
            'android_platform': 'android-' + str(self._conanfile.settings.os.api_level),
            'android_abi': android_abi(self._conanfile),
            'android_stl': libcxx_str,
            'android_ndk_path': android_ndk_path,
            'android_use_legacy_toolchain_file': use_cmake_legacy_toolchain,
        }
        return ctxt_toolchain


class AppleSystemBlock(Block):
    template = textwrap.dedent("""
        # Set the architectures for which to build.
        set(CMAKE_OSX_ARCHITECTURES {{ cmake_osx_architectures }} CACHE STRING "" FORCE)
        # Setting CMAKE_OSX_SYSROOT SDK, when using Xcode generator the name is enough
        # but full path is necessary for others
        set(CMAKE_OSX_SYSROOT {{ cmake_osx_sysroot }} CACHE STRING "" FORCE)
        {% if cmake_osx_deployment_target is defined %}
        # Setting CMAKE_OSX_DEPLOYMENT_TARGET if "os.version" is defined by the used conan profile
        set(CMAKE_OSX_DEPLOYMENT_TARGET "{{ cmake_osx_deployment_target }}" CACHE STRING "")
        {% endif %}
        set(BITCODE "")
        set(FOBJC_ARC "")
        set(VISIBILITY "")
        {% if enable_bitcode %}
        # Bitcode ON
        set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "YES")
        set(CMAKE_XCODE_ATTRIBUTE_BITCODE_GENERATION_MODE "bitcode")
        {% if enable_bitcode_marker %}
        set(BITCODE "-fembed-bitcode-marker")
        {% else %}
        set(BITCODE "-fembed-bitcode")
        {% endif %}
        {% elif enable_bitcode is not none %}
        # Bitcode OFF
        set(CMAKE_XCODE_ATTRIBUTE_ENABLE_BITCODE "NO")
        {% endif %}
        {% if enable_arc %}
        # ARC ON
        set(FOBJC_ARC "-fobjc-arc")
        set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC "YES")
        {% elif enable_arc is not none %}
        # ARC OFF
        set(FOBJC_ARC "-fno-objc-arc")
        set(CMAKE_XCODE_ATTRIBUTE_CLANG_ENABLE_OBJC_ARC "NO")
        {% endif %}
        {% if enable_visibility %}
        # Visibility ON
        set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN "NO")
        set(VISIBILITY "-fvisibility=default")
        {% elif enable_visibility is not none %}
        # Visibility OFF
        set(VISIBILITY "-fvisibility=hidden -fvisibility-inlines-hidden")
        set(CMAKE_XCODE_ATTRIBUTE_GCC_SYMBOLS_PRIVATE_EXTERN "YES")
        {% endif %}
        #Check if Xcode generator is used, since that will handle these flags automagically
        if(CMAKE_GENERATOR MATCHES "Xcode")
          message(DEBUG "Not setting any manual command-line buildflags, since Xcode is selected as generator.")
        else()
            string(APPEND CONAN_C_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")
            string(APPEND CONAN_CXX_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")
        endif()
        """)

    def context(self):
        if not is_apple_os(self._conanfile):
            return None

        def to_apple_archs(conanfile):
            f"""converts conan-style architectures into Apple-style archs
            to be used by CMake also supports multiple architectures
            separated by '{universal_arch_separator}'"""
            arch_ = conanfile.settings.get_safe("arch") if conanfile else None
            if arch_ is not None:
                return ";".join([_to_apple_arch(arch, default=arch) for arch in
                                 arch_.split(universal_arch_separator)])

        # check valid combinations of architecture - os ?
        # for iOS a FAT library valid for simulator and device can be generated
        # if multiple archs are specified "-DCMAKE_OSX_ARCHITECTURES=armv7;armv7s;arm64;i386;x86_64"
        host_architecture = to_apple_archs(self._conanfile)

        host_os_version = self._conanfile.settings.get_safe("os.version")
        host_sdk_name = self._conanfile.conf.get("tools.apple:sdk_path") or get_apple_sdk_fullname(self._conanfile)
        is_debug = self._conanfile.settings.get_safe('build_type') == "Debug"

        # Reading some configurations to enable or disable some Xcode toolchain flags and variables
        # Issue related: https://github.com/conan-io/conan/issues/9448
        # Based on https://github.com/leetal/ios-cmake repository
        enable_bitcode = self._conanfile.conf.get("tools.apple:enable_bitcode", check_type=bool)
        enable_arc = self._conanfile.conf.get("tools.apple:enable_arc", check_type=bool)
        enable_visibility = self._conanfile.conf.get("tools.apple:enable_visibility", check_type=bool)

        ctxt_toolchain = {
            "enable_bitcode": enable_bitcode,
            "enable_bitcode_marker": all([enable_bitcode, is_debug]),
            "enable_arc": enable_arc,
            "enable_visibility": enable_visibility
        }
        if host_sdk_name:
            host_sdk_name = relativize_path(host_sdk_name, self._conanfile,
                                            "${CMAKE_CURRENT_LIST_DIR}")
            ctxt_toolchain["cmake_osx_sysroot"] = host_sdk_name
        # this is used to initialize the OSX_ARCHITECTURES property on each target as it is created
        if host_architecture:
            ctxt_toolchain["cmake_osx_architectures"] = host_architecture

        if host_os_version:
            # https://cmake.org/cmake/help/latest/variable/CMAKE_OSX_DEPLOYMENT_TARGET.html
            # Despite the OSX part in the variable name(s) they apply also to other SDKs than
            # macOS like iOS, tvOS, watchOS or visionOS.
            ctxt_toolchain["cmake_osx_deployment_target"] = host_os_version

        return ctxt_toolchain


class FindFiles(Block):
    template = textwrap.dedent("""
        {% if find_package_prefer_config %}
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG {{ find_package_prefer_config }})
        {% endif %}

        # Definition of CMAKE_MODULE_PATH
        {% if build_paths %}
        list(PREPEND CMAKE_MODULE_PATH {{ build_paths }})
        {% endif %}
        {% if generators_folder %}
        # the generators folder (where conan generates files, like this toolchain)
        list(PREPEND CMAKE_MODULE_PATH {{ generators_folder }})
        {% endif %}

        # Definition of CMAKE_PREFIX_PATH, CMAKE_XXXXX_PATH
        {% if build_paths %}
        # The explicitly defined "builddirs" of "host" context dependencies must be in PREFIX_PATH
        list(PREPEND CMAKE_PREFIX_PATH {{ build_paths }})
        {% endif %}
        {% if generators_folder %}
        # The Conan local "generators" folder, where this toolchain is saved.
        list(PREPEND CMAKE_PREFIX_PATH {{ generators_folder }} )
        {% endif %}
        {% if cmake_program_path %}
        list(PREPEND CMAKE_PROGRAM_PATH {{ cmake_program_path }})
        {% endif %}
        {% if cmake_library_path %}
        list(PREPEND CMAKE_LIBRARY_PATH {{ cmake_library_path }})
        {% endif %}
        {% if is_apple and cmake_framework_path %}
        list(PREPEND CMAKE_FRAMEWORK_PATH {{ cmake_framework_path }})
        {% endif %}
        {% if cmake_include_path %}
        list(PREPEND CMAKE_INCLUDE_PATH {{ cmake_include_path }})
        {% endif %}
        {% if host_runtime_dirs %}
        set(CONAN_RUNTIME_LIB_DIRS {{ host_runtime_dirs }} )
        {% endif %}

        {% if cross_building %}
        if(NOT DEFINED CMAKE_FIND_ROOT_PATH_MODE_PACKAGE OR CMAKE_FIND_ROOT_PATH_MODE_PACKAGE STREQUAL "ONLY")
            set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE "BOTH")
        endif()
        if(NOT DEFINED CMAKE_FIND_ROOT_PATH_MODE_PROGRAM OR CMAKE_FIND_ROOT_PATH_MODE_PROGRAM STREQUAL "ONLY")
            set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM "BOTH")
        endif()
        if(NOT DEFINED CMAKE_FIND_ROOT_PATH_MODE_LIBRARY OR CMAKE_FIND_ROOT_PATH_MODE_LIBRARY STREQUAL "ONLY")
            set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY "BOTH")
        endif()
        {% if is_apple %}
        if(NOT DEFINED CMAKE_FIND_ROOT_PATH_MODE_FRAMEWORK OR CMAKE_FIND_ROOT_PATH_MODE_FRAMEWORK STREQUAL "ONLY")
            set(CMAKE_FIND_ROOT_PATH_MODE_FRAMEWORK "BOTH")
        endif()
        {% endif %}
        if(NOT DEFINED CMAKE_FIND_ROOT_PATH_MODE_INCLUDE OR CMAKE_FIND_ROOT_PATH_MODE_INCLUDE STREQUAL "ONLY")
            set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE "BOTH")
        endif()
        {% endif %}
    """)

    def _runtime_dirs_value(self, dirs):
        if is_multi_configuration(self._toolchain.generator):
            return ' '.join(f'"$<$<CONFIG:{c}>:{i}>"' for c, v in dirs.items() for i in v)
        else:
            return ' '.join(f'"{item}"' for _, items in dirs.items() for item in items)

    def _get_host_runtime_dirs(self, host_req):
        settings = self._conanfile.settings
        host_runtime_dirs = {}
        is_win = self._conanfile.settings.get_safe("os") == "Windows"

        # Get the previous configuration
        if is_multi_configuration(self._toolchain.generator) and os.path.exists(CONAN_TOOLCHAIN_FILENAME):
            existing_toolchain = load(CONAN_TOOLCHAIN_FILENAME)
            pattern_lib_dirs = r"set\(CONAN_RUNTIME_LIB_DIRS ([^)]*)\)"
            variable_match = re.search(pattern_lib_dirs, existing_toolchain)
            if variable_match:
                capture = variable_match.group(1)
                matches = re.findall(r'"\$<\$<CONFIG:([A-Za-z]*)>:([^>]*)>"', capture)
                host_runtime_dirs = {}
                for k, v in matches:
                    host_runtime_dirs.setdefault(k, []).append(v)

        # Calculate the dirs for the current build_type
        runtime_dirs = []
        for req in host_req:
            cppinfo = req.cpp_info.aggregated_components()
            runtime_dirs.extend(cppinfo.bindirs if is_win else cppinfo.libdirs)

        build_type = settings.get_safe("build_type")
        host_runtime_dirs[build_type] = [s.replace("\\", "/") for s in runtime_dirs]

        return host_runtime_dirs

    def _join_paths(self, paths):
        paths = [p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"') for p in paths]
        paths = [relativize_path(p, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}") for p in paths]
        return " ".join([f'"{p}"' for p in paths])

    def context(self):
        # To find the generated cmake_find_package finders
        # TODO: Change this for parameterized output location of CMakeDeps
        find_package_prefer_config = "ON"  # assume ON by default if not specified in conf
        prefer_config = self._conanfile.conf.get("tools.cmake.cmaketoolchain:find_package_prefer_config",
                                                 check_type=bool)
        if prefer_config is False:
            find_package_prefer_config = "OFF"

        is_apple_ = is_apple_os(self._conanfile)

        # Read information from host context
        # TODO: Add here in 2.0 the "skip": False trait
        host_req = self._conanfile.dependencies.filter({"build": False}).values()
        build_paths = []
        host_lib_paths = []
        host_runtime_dirs = self._get_host_runtime_dirs(host_req)
        host_framework_paths = []
        host_include_paths = []
        for req in host_req:
            cppinfo = req.cpp_info.aggregated_components()
            build_paths.extend(cppinfo.builddirs)
            host_lib_paths.extend(cppinfo.libdirs)
            if is_apple_:
                host_framework_paths.extend(cppinfo.frameworkdirs)
            host_include_paths.extend(cppinfo.includedirs)

        # Read information from build context
        build_req = self._conanfile.dependencies.build.values()
        build_bin_paths = []
        for req in build_req:
            cppinfo = req.cpp_info.aggregated_components()
            build_paths.extend(cppinfo.builddirs)
            build_bin_paths.extend(cppinfo.bindirs)

        return {
            "find_package_prefer_config": find_package_prefer_config,
            "generators_folder": "${CMAKE_CURRENT_LIST_DIR}",
            "build_paths": self._join_paths(build_paths),
            "cmake_program_path": self._join_paths(build_bin_paths),
            "cmake_library_path": self._join_paths(host_lib_paths),
            "cmake_framework_path": self._join_paths(host_framework_paths),
            "cmake_include_path": self._join_paths(host_include_paths),
            "is_apple": is_apple_,
            "cross_building": cross_building(self._conanfile),
            "host_runtime_dirs": self._runtime_dirs_value(host_runtime_dirs)
        }


class PkgConfigBlock(Block):
    template = textwrap.dedent("""
        {% if pkg_config %}
        set(PKG_CONFIG_EXECUTABLE {{ pkg_config }} CACHE FILEPATH "pkg-config executable")
        {% endif %}
        {% if pkg_config_path %}
        if (DEFINED ENV{PKG_CONFIG_PATH})
        set(ENV{PKG_CONFIG_PATH} "{{ pkg_config_path }}$ENV{PKG_CONFIG_PATH}")
        else()
        set(ENV{PKG_CONFIG_PATH} "{{ pkg_config_path }}")
        endif()
        {% endif %}
        """)

    def context(self):
        pkg_config = self._conanfile.conf.get("tools.gnu:pkg_config", check_type=str)
        if pkg_config:
            pkg_config = pkg_config.replace("\\", "/")
        subsystem = deduce_subsystem(self._conanfile, "build")
        pathsep = ":" if subsystem != WINDOWS else ";"
        pkg_config_path = "${CMAKE_CURRENT_LIST_DIR}" + pathsep
        return {"pkg_config": pkg_config,
                "pkg_config_path": pkg_config_path}


class UserToolchain(Block):
    template = textwrap.dedent("""
        {% for user_toolchain in paths %}
        include("{{user_toolchain}}")
        {% endfor %}
        """)

    def context(self):
        # This is global [conf] injection of extra toolchain files
        user_toolchain = self._conanfile.conf.get("tools.cmake.cmaketoolchain:user_toolchain",
                                                  default=[], check_type=list)
        paths = [relativize_path(p, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
                 for p in user_toolchain]
        paths = [p.replace("\\", "/") for p in paths]
        return {"paths": paths}


class ExtraFlagsBlock(Block):
    """This block is adding flags directly from user [conf] section"""

    _template = textwrap.dedent("""
        # Conan conf flags start: {{config}}
        {% if cxxflags %}
        string(APPEND CONAN_CXX_FLAGS{{suffix}} "{% for cxxflag in cxxflags %} {{ cxxflag }}{% endfor %}")
        {% endif %}
        {% if cflags %}
        string(APPEND CONAN_C_FLAGS{{suffix}} "{% for cflag in cflags %} {{ cflag }}{% endfor %}")
        {% endif %}
        {% if sharedlinkflags %}
        string(APPEND CONAN_SHARED_LINKER_FLAGS{{suffix}} "{% for sharedlinkflag in sharedlinkflags %} {{ sharedlinkflag }}{% endfor %}")
        {% endif %}
        {% if exelinkflags %}
        string(APPEND CONAN_EXE_LINKER_FLAGS{{suffix}} "{% for exelinkflag in exelinkflags %} {{ exelinkflag }}{% endfor %}")
        {% endif %}
        {% if defines %}
        {% if config %}
        {% for define in defines %}
        add_compile_definitions($<$<CONFIG:{{config}}>:"{{ define }}">)
        {% endfor %}
        {% else %}
        add_compile_definitions({% for define in defines %} "{{ define }}"{% endfor %})
        {% endif %}
        {% endif %}
        # Conan conf flags end
    """)

    @property
    def template(self):
        if not is_multi_configuration(self._toolchain.generator):
            return self._template

        sections = {}
        if os.path.exists(CONAN_TOOLCHAIN_FILENAME):
            existing_toolchain = load(CONAN_TOOLCHAIN_FILENAME)
            lines = existing_toolchain.splitlines()
            current_section = None
            for line in lines:
                if line.startswith("# Conan conf flags start: "):
                    section_name = line.split(":", 1)[1].strip()
                    current_section = [line]
                    sections[section_name] = current_section
                elif line == "# Conan conf flags end":
                    current_section.append(line)
                    current_section = None
                elif current_section is not None:
                    current_section.append(line)
            sections.pop("", None)  # Just in case it had a single config before

        config = self._conanfile.settings.get_safe("build_type")
        for k, v in sections.items():
            if k != config:
                v.insert(0, "{% raw %}")
                v.append("{% endraw %}")
        sections[config] = [self._template]
        sections = ["\n".join(lines) for lines in sections.values()]
        sections = "\n".join(sections)
        return sections

    def context(self):
        # Now, it's time to get all the flags defined by the user
        cxxflags = self._toolchain.extra_cxxflags + self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        cflags = self._toolchain.extra_cflags + self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        sharedlinkflags = self._toolchain.extra_sharedlinkflags + self._conanfile.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        exelinkflags = self._toolchain.extra_exelinkflags + self._conanfile.conf.get("tools.build:exelinkflags", default=[], check_type=list)
        defines = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)

        # See https://github.com/conan-io/conan/issues/13374
        android_ndk_path = self._conanfile.conf.get("tools.android:ndk_path")
        android_legacy_toolchain = self._conanfile.conf.get("tools.android:cmake_legacy_toolchain",
                                                            check_type=bool)
        if android_ndk_path and (cxxflags or cflags) and android_legacy_toolchain is not False:
            self._conanfile.output.warning("tools.build:cxxflags or cflags are defined, but Android NDK toolchain may be overriding "
                                           "the values. Consider setting tools.android:cmake_legacy_toolchain to False.")

        config = ""
        suffix = ""
        if is_multi_configuration(self._toolchain.generator):
            config = self._conanfile.settings.get_safe("build_type")
            suffix = f"_{config.upper()}" if config else ""
        return {
            "config": config,
            "suffix": suffix,
            "cxxflags": cxxflags,
            "cflags": cflags,
            "sharedlinkflags": sharedlinkflags,
            "exelinkflags": exelinkflags,
            "defines": [define.replace('"', '\\"') for define in defines]
        }


class CMakeFlagsInitBlock(Block):
    template = textwrap.dedent("""
        foreach(config IN LISTS CMAKE_CONFIGURATION_TYPES)
            string(TOUPPER ${config} config)
            if(DEFINED CONAN_CXX_FLAGS_${config})
              string(APPEND CMAKE_CXX_FLAGS_${config}_INIT " ${CONAN_CXX_FLAGS_${config}}")
            endif()
            if(DEFINED CONAN_C_FLAGS_${config})
              string(APPEND CMAKE_C_FLAGS_${config}_INIT " ${CONAN_C_FLAGS_${config}}")
            endif()
            if(DEFINED CONAN_SHARED_LINKER_FLAGS_${config})
              string(APPEND CMAKE_SHARED_LINKER_FLAGS_${config}_INIT " ${CONAN_SHARED_LINKER_FLAGS_${config}}")
            endif()
            if(DEFINED CONAN_EXE_LINKER_FLAGS_${config})
              string(APPEND CMAKE_EXE_LINKER_FLAGS_${config}_INIT " ${CONAN_EXE_LINKER_FLAGS_${config}}")
            endif()
        endforeach()

        if(DEFINED CONAN_CXX_FLAGS)
          string(APPEND CMAKE_CXX_FLAGS_INIT " ${CONAN_CXX_FLAGS}")
        endif()
        if(DEFINED CONAN_C_FLAGS)
          string(APPEND CMAKE_C_FLAGS_INIT " ${CONAN_C_FLAGS}")
        endif()
        if(DEFINED CONAN_SHARED_LINKER_FLAGS)
          string(APPEND CMAKE_SHARED_LINKER_FLAGS_INIT " ${CONAN_SHARED_LINKER_FLAGS}")
        endif()
        if(DEFINED CONAN_EXE_LINKER_FLAGS)
          string(APPEND CMAKE_EXE_LINKER_FLAGS_INIT " ${CONAN_EXE_LINKER_FLAGS}")
        endif()

        """)


class TryCompileBlock(Block):
    template = textwrap.dedent("""
        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()
        """)


class CompilersBlock(Block):
    template = textwrap.dedent(r"""
        {% for lang, compiler_path in compilers.items() %}
        set(CMAKE_{{ lang }}_COMPILER "{{ compiler_path|replace('\\', '/') }}")
        {% endfor %}
    """)

    def context(self):
        # Reading configuration from "tools.build:compiler_executables" -> {"C": "/usr/bin/gcc"}
        compilers_by_conf = self._conanfile.conf.get("tools.build:compiler_executables", default={},
                                                     check_type=dict)
        # Map the possible languages
        compilers = {}
        # Allowed <LANG> variables (and <LANG>_LAUNCHER)
        compilers_mapping = {"c": "C", "cuda": "CUDA", "cpp": "CXX", "objc": "OBJC",
                             "objcpp": "OBJCXX", "rc": "RC", 'fortran': "Fortran", 'asm': "ASM",
                             "hip": "HIP", "ispc": "ISPC"}
        for comp, lang in compilers_mapping.items():
            # To set CMAKE_<LANG>_COMPILER
            if comp in compilers_by_conf:
                compilers[lang] = compilers_by_conf[comp]
        return {"compilers": compilers}


class GenericSystemBlock(Block):
    template = textwrap.dedent("""
        ########## generic_system block #############
        # Definition of system, platform and toolset
        #############################################
        {% if cmake_sysroot %}
        set(CMAKE_SYSROOT {{ cmake_sysroot }})
        {% endif %}

        {% if cmake_system_name %}
        # Cross building
        set(CMAKE_SYSTEM_NAME {{ cmake_system_name }})
        {% endif %}
        {% if cmake_system_version %}
        set(CMAKE_SYSTEM_VERSION {{ cmake_system_version }})
        {% endif %}
        {% if cmake_system_processor %}
        set(CMAKE_SYSTEM_PROCESSOR {{ cmake_system_processor }})
        {% endif %}

        {% if generator_platform and not winsdk_version %}
        set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE)
        {% elif winsdk_version %}
        if(POLICY CMP0149)
            cmake_policy(GET CMP0149 _POLICY_WINSDK_VERSION)
        endif()
        if(_POLICY_WINSDK_VERSION STREQUAL "NEW")
            message(STATUS "Conan toolchain: CMAKE_GENERATOR_PLATFORM={{gen_platform_sdk_version}}")
            set(CMAKE_GENERATOR_PLATFORM "{{ gen_platform_sdk_version }}" CACHE STRING "" FORCE)
        else()
            # winsdk_version will be taken from above CMAKE_SYSTEM_VERSION
            message(STATUS "Conan toolchain: CMAKE_GENERATOR_PLATFORM={{generator_platform}}")
            set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE)
        endif()
        {% endif %}

        {% if toolset %}
        message(STATUS "Conan toolchain: CMAKE_GENERATOR_TOOLSET={{ toolset }}")
        set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE)
        {% endif %}
        """)

    @staticmethod
    def get_toolset(generator, conanfile):
        toolset = None
        if generator is None or ("Visual" not in generator and "Xcode" not in generator):
            return None
        settings = conanfile.settings
        compiler = settings.get_safe("compiler")
        if compiler == "intel-cc":
            return IntelCC(conanfile).ms_toolset
        elif compiler == "msvc":
            toolset = settings.get_safe("compiler.toolset")
            if toolset is None:
                compiler_version = str(settings.compiler.version)
                msvc_update = conanfile.conf.get("tools.microsoft:msvc_update")
                compiler_update = msvc_update or settings.get_safe("compiler.update")
                toolset = msvc_version_to_toolset_version(compiler_version)
                if compiler_update is not None:  # It is full one(19.28), not generic 19.2X
                    # The equivalent of compiler 19.26 is toolset 14.26
                    toolset += ",version=14.{}{}".format(compiler_version[-1], compiler_update)
        elif compiler == "clang":
            if generator and "Visual" in generator:
                if "Visual Studio 16" in generator or "Visual Studio 17" in generator:
                    toolset = "ClangCL"
                else:
                    raise ConanException("CMakeToolchain with compiler=clang and a CMake "
                                         "'Visual Studio' generator requires VS16 or VS17")
        toolset_arch = conanfile.conf.get("tools.cmake.cmaketoolchain:toolset_arch")
        if toolset_arch is not None:
            toolset_arch = "host={}".format(toolset_arch)
            toolset = toolset_arch if toolset is None else "{},{}".format(toolset, toolset_arch)
        toolset_cuda = conanfile.conf.get("tools.cmake.cmaketoolchain:toolset_cuda")
        if toolset_cuda is not None:
            toolset_cuda = relativize_path(toolset_cuda, conanfile, "${CMAKE_CURRENT_LIST_DIR}")
            toolset_cuda = f"cuda={toolset_cuda}"
            toolset = toolset_cuda if toolset is None else f"{toolset},{toolset_cuda}"
        return toolset

    @staticmethod
    def get_generator_platform(generator, conanfile):
        settings = conanfile.settings
        # Returns the generator platform to be used by CMake
        compiler = settings.get_safe("compiler")
        arch = settings.get_safe("arch")

        if settings.get_safe("os") == "WindowsCE":
            return settings.get_safe("os.platform")

        if compiler in ("msvc", "clang") and generator and "Visual" in generator:
            return {"x86": "Win32",
                    "x86_64": "x64",
                    "armv7": "ARM",
                    "armv8": "ARM64",
                    "arm64ec": "ARM64EC"}.get(arch)
        return None

    def _get_generic_system_name(self):
        os_host = self._conanfile.settings.get_safe("os")
        os_build = self._conanfile.settings_build.get_safe("os")
        arch_host = self._conanfile.settings.get_safe("arch")
        arch_build = self._conanfile.settings_build.get_safe("arch")
        cmake_system_name_map = {"Neutrino": "QNX",
                                 "": "Generic",
                                 "baremetal": "Generic",
                                 None: "Generic"}
        if os_host != os_build:
            return cmake_system_name_map.get(os_host, os_host)
        elif arch_host is not None and arch_host != arch_build:
            if not ((arch_build == "x86_64") and (arch_host == "x86") or
                    (arch_build == "sparcv9") and (arch_host == "sparc") or
                    (arch_build == "ppc64") and (arch_host == "ppc32")):
                return cmake_system_name_map.get(os_host, os_host)

    def _is_apple_cross_building(self):

        if is_universal_arch(self._conanfile.settings.get_safe("arch"),
                             self._conanfile.settings.possible_values().get("arch")):
            return False

        os_host = self._conanfile.settings.get_safe("os")
        arch_host = self._conanfile.settings.get_safe("arch")
        arch_build = self._conanfile.settings_build.get_safe("arch")
        os_build = self._conanfile.settings_build.get_safe("os")
        return os_host in ('iOS', 'watchOS', 'tvOS', 'visionOS') or (
                os_host == 'Macos' and (arch_host != arch_build or os_build != os_host))

    def _get_darwin_version(self, os_name, os_version):
        # version mapping from https://en.wikipedia.org/wiki/Darwin_(operating_system)
        version_mapping = {
            "Macos": {
                "10.6": "10", "10.7": "11", "10.8": "12", "10.9": "13", "10.10": "14", "10.11": "15",
                "10.12": "16", "10.13": "17", "10.14": "18", "10.15": "19", "11": "20", "12": "21",
                "13": "22", "14": "23",
            },
            "iOS": {
                "7": "14", "8": "14", "9": "15", "10": "16", "11": "17", "12": "18", "13": "19",
                "14": "20", "15": "21", "16": "22", "17": "23"
            },
            "watchOS": {
                "4": "17", "5": "18", "6": "19", "7": "20",
                "8": "21", "9": "22", "10": "23"
            },
            "tvOS": {
                "11": "17", "12": "18", "13": "19", "14": "20",
                "15": "21", "16": "22", "17": "23"
            },
            "visionOS": {
                "1": "23"
            }
        }
        os_version = Version(os_version).major if os_name != "Macos" or (os_name == "Macos" and Version(
            os_version) >= Version("11")) else os_version
        return version_mapping.get(os_name, {}).get(str(os_version))

    def _get_cross_build(self):
        user_toolchain = self._conanfile.conf.get("tools.cmake.cmaketoolchain:user_toolchain")

        system_name = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_name")
        system_version = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_version")
        system_processor = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_processor")

        # try to detect automatically
        if not user_toolchain and not is_universal_arch(self._conanfile.settings.get_safe("arch"),
                                                        self._conanfile.settings.possible_values().get("arch")):
            os_host = self._conanfile.settings.get_safe("os")
            os_host_version = self._conanfile.settings.get_safe("os.version")
            arch_host = self._conanfile.settings.get_safe("arch")
            if arch_host == "armv8":
                arch_host = {"Windows": "ARM64", "Macos": "arm64"}.get(os_host, "aarch64")

            if system_name is None:  # Try to deduce
                _system_version = None
                _system_processor = None
                if self._is_apple_cross_building():
                    # cross-build in Macos also for M1
                    system_name = {'Macos': 'Darwin'}.get(os_host, os_host)
                    #  CMAKE_SYSTEM_VERSION for Apple sets the Darwin version, not the os version
                    _system_version = self._get_darwin_version(os_host, os_host_version)
                    _system_processor = to_apple_arch(self._conanfile)
                elif os_host != 'Android':
                    system_name = self._get_generic_system_name()
                    _system_version = os_host_version
                    _system_processor = arch_host

                if system_name is not None and system_version is None:
                    system_version = _system_version
                if system_name is not None and system_processor is None:
                    system_processor = _system_processor

        return system_name, system_version, system_processor

    def _get_winsdk_version(self, system_version, generator_platform):
        compiler = self._conanfile.settings.get_safe("compiler")
        if compiler not in ("msvc", "clang") or "Visual" not in str(self._toolchain.generator):
            # Ninja will get it from VCVars, not from toolchain
            return system_version, None, None

        winsdk_version = self._conanfile.conf.get("tools.microsoft:winsdk_version", check_type=str)
        if winsdk_version:
            if system_version:
                self._conanfile.output.warning("Both cmake_system_version and winsdk_version confs"
                                               " defined, prioritizing winsdk_version")
            system_version = winsdk_version
        elif "Windows" in self._conanfile.settings.get_safe("os", ""):
            winsdk_version = self._conanfile.settings.get_safe("os.version")
            if system_version:
                if winsdk_version:
                    self._conanfile.output.warning("Both cmake_system_version conf and os.version"
                                                   " defined, prioritizing cmake_system_version")
                winsdk_version = system_version

        gen_platform_sdk_version = [generator_platform,
                                    f"version={winsdk_version}" if winsdk_version else None]
        gen_platform_sdk_version = ",".join(d for d in gen_platform_sdk_version if d)

        return system_version, winsdk_version, gen_platform_sdk_version

    def context(self):
        generator = self._toolchain.generator
        generator_platform = self.get_generator_platform(generator, self._conanfile)
        toolset = self.get_toolset(generator, self._conanfile)
        system_name, system_version, system_processor = self._get_cross_build()

        # This is handled by the tools.apple:sdk_path and CMAKE_OSX_SYSROOT in Apple
        cmake_sysroot = self._conanfile.conf.get("tools.build:sysroot")
        cmake_sysroot = cmake_sysroot.replace("\\", "/") if cmake_sysroot is not None else None
        if cmake_sysroot is not None:
            cmake_sysroot = relativize_path(cmake_sysroot, self._conanfile,
                                            "${CMAKE_CURRENT_LIST_DIR}")

        result = self._get_winsdk_version(system_version, generator_platform)
        system_version, winsdk_version, gen_platform_sdk_version = result

        return {"toolset": toolset,
                "generator_platform": generator_platform,
                "cmake_system_name": system_name,
                "cmake_system_version": system_version,
                "cmake_system_processor": system_processor,
                "cmake_sysroot": cmake_sysroot,
                "winsdk_version": winsdk_version,
                "gen_platform_sdk_version": gen_platform_sdk_version}

class ExtraVariablesBlock(Block):
    template = textwrap.dedent(r"""
        {% if extra_variables %}
        {% for key, value in extra_variables.items() %}
        set({{ key }} {{ value }})
        {% endfor %}
        {% endif %}
    """)

    CMAKE_CACHE_TYPES = ["BOOL","FILEPATH", "PATH", "STRING", "INTERNAL"]

    def get_exact_type(self, key, value):
        if isinstance(value, str):
            return f"\"{value}\""
        elif isinstance(value, (int, float)):
            return value
        elif isinstance(value, dict):
            var_value = self.get_exact_type(key, value.get("value"))
            is_cache = value.get("cache")
            if is_cache:
                if not isinstance(is_cache, bool):
                    raise ConanException(f'tools.cmake.cmaketoolchain:extra_variables "cache" must be a boolean (True/False)')
                var_type = value.get("type")
                if not var_type:
                    raise ConanException(f'tools.cmake.cmaketoolchain:extra_variables needs "type" defined for cache variable "{key}"')
                if var_type not in self.CMAKE_CACHE_TYPES:
                    raise ConanException(f'tools.cmake.cmaketoolchain:extra_variables invalid type "{var_type}" for cache variable "{key}". Possible types: {", ".join(self.CMAKE_CACHE_TYPES)}')
                # Set docstring as variable name if not defined
                docstring = value.get("docstring") or key
                return f"{var_value} CACHE {var_type} \"{docstring}\""
            else:
                return var_value

    def context(self):
        # Reading configuration from "tools.cmake.cmaketoolchain:extra_variables"
        extra_variables = self._conanfile.conf.get("tools.cmake.cmaketoolchain:extra_variables", default={}, check_type=dict)
        parsed_extra_variables = {}
        for key, value in extra_variables.items():
            parsed_extra_variables[key] = self.get_exact_type(key, value)
        return {"extra_variables": parsed_extra_variables}

class OutputDirsBlock(Block):

    @property
    def template(self):
        return textwrap.dedent("""
           {% if package_folder %}
           set(CMAKE_INSTALL_PREFIX "{{package_folder}}")
           {% endif %}
           {% if default_bin %}
           set(CMAKE_INSTALL_BINDIR "{{default_bin}}")
           set(CMAKE_INSTALL_SBINDIR "{{default_bin}}")
           set(CMAKE_INSTALL_LIBEXECDIR "{{default_bin}}")
           {% endif %}
           {% if default_lib %}
           set(CMAKE_INSTALL_LIBDIR "{{default_lib}}")
           {% endif %}
           {% if default_include %}
           set(CMAKE_INSTALL_INCLUDEDIR "{{default_include}}")
           set(CMAKE_INSTALL_OLDINCLUDEDIR "{{default_include}}")
           {% endif %}
           {% if default_res %}
           set(CMAKE_INSTALL_DATAROOTDIR "{{default_res}}")
           {% endif %}
        """)

    def _get_cpp_info_value(self, name):
        # Why not taking cpp.build? because this variables are used by the "cmake install"
        # that correspond to the package folder (even if the root is the build directory)
        elements = getattr(self._conanfile.cpp.package, name)
        return elements[0] if elements else None

    def context(self):
        pf = self._conanfile.package_folder
        return {"package_folder": pf.replace("\\", "/") if pf else None,
                "default_bin": self._get_cpp_info_value("bindirs"),
                "default_lib": self._get_cpp_info_value("libdirs"),
                "default_include": self._get_cpp_info_value("includedirs"),
                "default_res": self._get_cpp_info_value("resdirs")}


class ToolchainBlocks:
    def __init__(self, conanfile, toolchain, items=None):
        self._blocks = OrderedDict()
        self._conanfile = conanfile
        self._toolchain = toolchain
        if items:
            for name, block in items:
                self._blocks[name] = block(conanfile, toolchain)

    def keys(self):
        return self._blocks.keys()

    def items(self):
        return self._blocks.items()

    def remove(self, name, *args):
        del self._blocks[name]
        for arg in args:
            del self._blocks[arg]

    def select(self, name, *args):
        """
        keep the blocks provided as arguments, remove the others
        """
        to_keep = [name] + list(args)
        self._blocks = OrderedDict((k, v) for k, v in self._blocks.items() if k in to_keep)

    def __setitem__(self, name, block_type):
        # Create a new class inheriting Block with the elements of the provided one
        block_type = type('proxyUserBlock', (Block,), dict(block_type.__dict__))
        self._blocks[name] = block_type(self._conanfile, self._toolchain)

    def __getitem__(self, name):
        return self._blocks[name]

    def process_blocks(self):
        result = []
        for b in self._blocks.values():
            content = b.get_rendered_content()
            if content:
                result.append(content)
        return result
