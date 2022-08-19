import os
import re
import textwrap
from collections import OrderedDict

from jinja2 import Template

from conan.tools._compilers import architecture_flag
from conan.tools.apple.apple import is_apple_os, to_apple_arch
from conan.tools.build import build_jobs
from conan.tools.build.cross_building import cross_building
from conan.tools.cmake.toolchain import CONAN_TOOLCHAIN_FILENAME
from conan.tools.intel import IntelCC
from conan.tools.microsoft.visual import is_msvc, msvc_version_to_toolset_version
from conans.errors import ConanException
from conans.util.files import load


class ToolchainBlocks:
    def __init__(self, conanfile, toolchain, items=None):
        self._blocks = OrderedDict()
        self._conanfile = conanfile
        self._toolchain = toolchain
        if items:
            for name, block in items:
                self._blocks[name] = block(conanfile, toolchain)

    def remove(self, name):
        del self._blocks[name]

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

        def cmake_value(value):
            if isinstance(value, bool):
                return "ON" if value else "OFF"
            else:
                return '"{}"'.format(value)

        template = Template(self.template, trim_blocks=True, lstrip_blocks=True)
        template.environment.filters["cmake_value"] = cmake_value
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
        compiler = settings.get_safe("compiler")
        if compiler not in ("Visual Studio", "msvc", "intel-cc"):
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
        runtime = settings.get_safe("compiler.runtime")
        if compiler == "Visual Studio":
            config_dict[build_type] = {"MT": "MultiThreaded",
                                       "MTd": "MultiThreadedDebug",
                                       "MD": "MultiThreadedDLL",
                                       "MDd": "MultiThreadedDebugDLL"}[runtime]
        if compiler == "msvc" or compiler == "intel-cc":
            runtime_type = settings.get_safe("compiler.runtime_type")
            rt = "MultiThreadedDebug" if runtime_type == "Debug" else "MultiThreaded"
            if runtime != "static":
                rt += "DLL"
            config_dict[build_type] = rt
        return {"vs_runtimes": config_dict}


class FPicBlock(Block):
    template = textwrap.dedent("""
        {% if fpic %}
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE={{ fpic }} (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE {{ fpic }})
        {% endif %}
        """)

    def context(self):
        fpic = self._conanfile.options.get_safe("fPIC")
        if fpic is None:
            return None
        os_ = self._conanfile.settings.get_safe("os")
        if os_ and "Windows" in os_:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined for Windows")
            return None
        return {"fpic": "ON" if fpic else "OFF"}


class GLibCXXBlock(Block):
    template = textwrap.dedent("""
        {% if set_libcxx %}
        string(APPEND CONAN_CXX_FLAGS " {{ set_libcxx }}")
        {% endif %}
        {% if glibcxx %}
        add_compile_definitions(_GLIBCXX_USE_CXX11_ABI={{ glibcxx }})
        {% endif %}
        """)

    def context(self):
        libcxx = self._conanfile.settings.get_safe("compiler.libcxx")
        if not libcxx:
            return None
        compiler = self._conanfile.settings.get_safe("compiler")
        lib = glib = None
        if compiler == "apple-clang":
            # In apple-clang 2 only values atm are "libc++" and "libstdc++"
            lib = "-stdlib={}".format(libcxx)
        elif compiler == "clang" or compiler == "intel-cc":
            if libcxx == "libc++":
                lib = "-stdlib=libc++"
            elif libcxx == "libstdc++" or libcxx == "libstdc++11":
                lib = "-stdlib=libstdc++"
            # FIXME, something to do with the other values? Android c++_shared?
        elif compiler == "sun-cc":
            lib = {"libCstd": "Cstd",
                   "libstdcxx": "stdcxx4",
                   "libstlport": "stlport4",
                   "libstdc++": "stdcpp"
                   }.get(libcxx)
            if lib:
                lib = "-library={}".format(lib)

        if compiler in ['clang', 'apple-clang', 'gcc']:
            if libcxx == "libstdc++":
                glib = "0"
            elif libcxx == "libstdc++11" and self._conanfile.conf.get("tools.gnu:define_libcxx11_abi",
                                                                      check_type=bool):
                glib = "1"
        return {"set_libcxx": lib, "glibcxx": glib}


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


class CppStdBlock(Block):
    template = textwrap.dedent("""
        message(STATUS "Conan toolchain: C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
        set(CMAKE_CXX_STANDARD_REQUIRED ON)
        """)

    def context(self):
        compiler_cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        if compiler_cppstd is None:
            return None

        if compiler_cppstd.startswith("gnu"):
            cppstd = compiler_cppstd[3:]
            cppstd_extensions = "ON"
        else:
            cppstd = compiler_cppstd
            cppstd_extensions = "OFF"
        return {"cppstd": cppstd, "cppstd_extensions": cppstd_extensions}


class SharedLibBock(Block):
    template = textwrap.dedent("""
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS = {{ shared_libs }}")
        set(BUILD_SHARED_LIBS {{ shared_libs }})
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
        if compiler not in ("Visual Studio", "msvc") or "Visual" not in self._toolchain.generator:
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
        include({{ android_ndk_path }}/build/cmake/android.toolchain.cmake)
        """)

    def context(self):
        os_ = self._conanfile.settings.get_safe("os")
        if os_ != "Android":
            return

        android_abi = {"x86": "x86",
                       "x86_64": "x86_64",
                       "armv7": "armeabi-v7a",
                       "armv8": "arm64-v8a"}.get(str(self._conanfile.settings.arch))

        # TODO: only 'c++_shared' y 'c++_static' supported?
        #  https://developer.android.com/ndk/guides/cpp-support
        libcxx_str = self._conanfile.settings.get_safe("compiler.libcxx")

        android_ndk_path = self._conanfile.conf.get("tools.android:ndk_path")
        if not android_ndk_path:
            raise ConanException('CMakeToolchain needs tools.android:ndk_path configuration defined')
        android_ndk_path = android_ndk_path.replace("\\", "/")

        ctxt_toolchain = {
            'android_platform': 'android-' + str(self._conanfile.settings.os.api_level),
            'android_abi': android_abi,
            'android_stl': libcxx_str,
            'android_ndk_path': android_ndk_path,
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
            string(APPEND CONAN_C_FLAGS " ${BITCODE} ${FOBJC_ARC}")
            string(APPEND CONAN_CXX_FLAGS " ${BITCODE} ${VISIBILITY} ${FOBJC_ARC}")
        endif()
        """)

    def _apple_sdk_name(self):
        """
        Returns the value for the SDKROOT with this preference:
        - 1. The full path set in the conf with tools.apple:sdk_path
        - 2. osd.sdk + os.sdk_version
        Otherwise None
        Every user should specify it because there could be several ones depending
        on the OS architecture.

        Note: In case of MacOS it'll be the same for all the architectures.
        """
        os_ = self._conanfile.settings.get_safe('os')
        os_sdk = self._conanfile.settings.get_safe('os.sdk')
        os_sdk_version = self._conanfile.settings.get_safe('os.sdk_version') or ""
        sdk = self._conanfile.conf.get("tools.apple:sdk_path")

        if sdk:
            return sdk
        elif os_ == "Macos":  # if the host is Macos it can only be "macosx"
            return "{}{}".format("macosx", os_sdk_version)
        elif os_sdk:
            return "{}{}".format(os_sdk, os_sdk_version)
        else:
            raise ConanException("Please, specify a suitable value for os.sdk.")

    def context(self):
        os_ = self._conanfile.settings.get_safe("os")
        if not is_apple_os(self._conanfile):
            return None

        host_architecture = to_apple_arch(self._conanfile)
        host_os_version = self._conanfile.settings.get_safe("os.version")
        host_sdk_name = self._apple_sdk_name()
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
            ctxt_toolchain["cmake_osx_sysroot"] = host_sdk_name
        # this is used to initialize the OSX_ARCHITECTURES property on each target as it is created
        if host_architecture:
            ctxt_toolchain["cmake_osx_architectures"] = host_architecture

        if host_os_version:
            # https://cmake.org/cmake/help/latest/variable/CMAKE_OSX_DEPLOYMENT_TARGET.html
            # Despite the OSX part in the variable name(s) they apply also to other SDKs than
            # macOS like iOS, tvOS, or watchOS.
            ctxt_toolchain["cmake_osx_deployment_target"] = host_os_version

        return ctxt_toolchain


class FindFiles(Block):
    template = textwrap.dedent("""
        {% if find_package_prefer_config %}
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG {{ find_package_prefer_config }})
        {% endif %}

        # Definition of CMAKE_MODULE_PATH
        {% if build_build_paths %}
        # Explicitly defined "buildirs" of "build" context dependencies
        list(PREPEND CMAKE_MODULE_PATH {{ build_build_paths }})
        {% endif %}
        {% if host_build_paths_noroot %}
        # Explicitly defined "builddirs" of "host" dependencies
        list(PREPEND CMAKE_MODULE_PATH {{ host_build_paths_noroot }})
        {% endif %}
        {% if host_build_paths_root %}
        # The root (which is the default builddirs) path of dependencies in the host context
        list(PREPEND CMAKE_MODULE_PATH {{ host_build_paths_root }})
        {% endif %}
        {% if generators_folder %}
        # the generators folder (where conan generates files, like this toolchain)
        list(PREPEND CMAKE_MODULE_PATH {{ generators_folder }})
        {% endif %}

        # Definition of CMAKE_PREFIX_PATH, CMAKE_XXXXX_PATH
        {% if host_build_paths_noroot %}
        # The explicitly defined "builddirs" of "host" context dependencies must be in PREFIX_PATH
        list(PREPEND CMAKE_PREFIX_PATH {{ host_build_paths_noroot }})
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

    @staticmethod
    def _join_paths(paths):
        return " ".join(['"{}"'.format(p.replace('\\', '/')
                                        .replace('$', '\\$')
                                        .replace('"', '\\"')) for p in paths])

    def context(self):
        # To find the generated cmake_find_package finders
        # TODO: Change this for parameterized output location of CMakeDeps
        find_package_prefer_config = "ON"  # assume ON by default if not specified in conf
        prefer_config = self._conanfile.conf.get("tools.cmake.cmaketoolchain:find_package_prefer_config",
                                                 check_type=bool)
        if prefer_config is False:
            find_package_prefer_config = "OFF"

        os_ = self._conanfile.settings.get_safe("os")
        is_apple_ = is_apple_os(self._conanfile)

        # Read information from host context
        host_req = self._conanfile.dependencies.host.values()
        host_build_paths_root = []
        host_build_paths_noroot = []
        host_lib_paths = []
        host_framework_paths = []
        host_include_paths = []
        for req in host_req:
            cppinfo = req.cpp_info.aggregated_components()
            # If the builddir is the package_folder, then it is the default "root" one
            # The package_folder can be None if editable and layout(), in that case only the
            # host_build_paths_noroot will be populated
            if req.package_folder:
                nf = os.path.normpath(req.package_folder)
                host_build_paths_root.extend(p for p in cppinfo.builddirs if os.path.normpath(p) == nf)
                host_build_paths_noroot.extend(p for p in cppinfo.builddirs if os.path.normpath(p) != nf)
            else:
                host_build_paths_root = []
                host_build_paths_noroot.extend(p for p in cppinfo.builddirs)
            host_lib_paths.extend(cppinfo.libdirs)
            if is_apple_:
                host_framework_paths.extend(cppinfo.frameworkdirs)
            host_include_paths.extend(cppinfo.includedirs)

        # Read information from build context
        build_req = self._conanfile.dependencies.build.values()
        build_build_paths = []
        build_bin_paths = []
        for req in build_req:
            cppinfo = req.cpp_info.aggregated_components()
            build_build_paths.extend(cppinfo.builddirs)
            build_bin_paths.extend(cppinfo.bindirs)

        return {
            "find_package_prefer_config": find_package_prefer_config,
            "generators_folder": "${CMAKE_CURRENT_LIST_DIR}",
            "host_build_paths_root": self._join_paths(host_build_paths_root),
            "host_build_paths_noroot": self._join_paths(host_build_paths_noroot),
            "build_build_paths": self._join_paths(build_build_paths),
            "cmake_program_path": self._join_paths(build_bin_paths),
            "cmake_library_path": self._join_paths(host_lib_paths),
            "cmake_framework_path": self._join_paths(host_framework_paths),
            "cmake_include_path": self._join_paths(host_include_paths),
            "is_apple": is_apple_,
            "cross_building": cross_building(self._conanfile),
        }


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
        return {"paths": [ut.replace("\\", "/") for ut in user_toolchain]}


class ExtraFlagsBlock(Block):
    """This block is adding flags directly from user [conf] section"""

    template = textwrap.dedent("""
        # Extra c, cxx, linkflags and defines
        {% if cxxflags %}
        string(APPEND CONAN_CXX_FLAGS "{% for cxxflag in cxxflags %} {{ cxxflag }}{% endfor %}")
        {% endif %}
        {% if cflags %}
        string(APPEND CONAN_C_FLAGS "{% for cflag in cflags %} {{ cflag }}{% endfor %}")
        {% endif %}
        {% if sharedlinkflags %}
        string(APPEND CONAN_SHARED_LINKER_FLAGS "{% for sharedlinkflag in sharedlinkflags %} {{ sharedlinkflag }}{% endfor %}")
        {% endif %}
        {% if exelinkflags %}
        string(APPEND CONAN_EXE_LINKER_FLAGS "{% for exelinkflag in exelinkflags %} {{ exelinkflag }}{% endfor %}")
        {% endif %}
        {% if defines %}
        add_compile_definitions({% for define in defines %} "{{ define }}"{% endfor %})
        {% endif %}
    """)

    def context(self):
        # Now, it's time to get all the flags defined by the user
        cxxflags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        cflags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        sharedlinkflags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        exelinkflags = self._conanfile.conf.get("tools.build:exelinkflags", default=[], check_type=list)
        defines = self._conanfile.conf.get("tools.build:defines", default=[], check_type=list)
        return {
            "cxxflags": cxxflags,
            "cflags": cflags,
            "sharedlinkflags": sharedlinkflags,
            "exelinkflags": exelinkflags,
            "defines": [define.replace('"', '\\"') for define in defines]
        }


class CMakeFlagsInitBlock(Block):
    template = textwrap.dedent("""
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


class GenericSystemBlock(Block):
    template = textwrap.dedent("""
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

        {% if generator_platform %}
        set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE)
        {% endif %}
        {% if toolset %}
        set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE)
        {% endif %}
        {% if compiler %}
        if(NOT DEFINED ENV{CC})
        set(CMAKE_C_COMPILER {{ compiler }})
        endif()
        {% endif %}
        {% if compiler_cpp %}
        if(NOT DEFINED ENV{CXX})
        set(CMAKE_CXX_COMPILER {{ compiler_cpp }})
        endif()
        {% endif %}
        {% if compiler_rc %}
        if(NOT DEFINED ENV{RC})
        set(CMAKE_RC_COMPILER {{ compiler_rc }})
        endif()
        {% endif %}
        """)

    def _get_toolset(self, generator):
        if generator is None or ("Visual" not in generator and "Xcode" not in generator):
            return None
        settings = self._conanfile.settings
        compiler = settings.get_safe("compiler")
        compiler_base = settings.get_safe("compiler.base")
        toolset = None
        if compiler == "Visual Studio":
            toolset = settings.get_safe("compiler.toolset")
        elif compiler == "intel" and compiler_base == "Visual Studio" and "Visual" in generator:
            # TODO: This intel toolset needs to be validated too
            compiler_version = settings.get_safe("compiler.version")
            if compiler_version:
                compiler_version = compiler_version if "." in compiler_version else \
                    "%s.0" % compiler_version
                toolset = "Intel C++ Compiler " + compiler_version
        elif compiler == "intel-cc":
            return IntelCC(self._conanfile).ms_toolset
        elif compiler == "msvc":
            toolset = settings.get_safe("compiler.toolset")
            if toolset is None:
                compiler_version = str(settings.compiler.version)
                compiler_update = str(settings.compiler.update)
                if compiler_update != "None":  # It is full one(19.28), not generic 19.2X
                    # The equivalent of compiler 19.26 is toolset 14.26
                    toolset = "version=14.{}{}".format(compiler_version[-1], compiler_update)
                else:
                    toolset = msvc_version_to_toolset_version(compiler_version)
        elif compiler == "clang":
            if generator and "Visual" in generator:
                if "Visual Studio 16" in generator:
                    toolset = "ClangCL"
                else:
                    raise ConanException("CMakeToolchain compiler=clang only supported VS 16")
        toolset_arch = self._conanfile.conf.get("tools.cmake.cmaketoolchain:toolset_arch")
        if toolset_arch is not None:
            toolset_arch = "host={}".format(toolset_arch)
            toolset = toolset_arch if toolset is None else "{},{}".format(toolset, toolset_arch)
        return toolset

    def _get_generator_platform(self, generator):
        settings = self._conanfile.settings
        # Returns the generator platform to be used by CMake
        compiler = settings.get_safe("compiler")
        compiler_base = settings.get_safe("compiler.base")
        arch = settings.get_safe("arch")

        if settings.get_safe("os") == "WindowsCE":
            return settings.get_safe("os.platform")

        if (compiler in ("Visual Studio", "msvc") or compiler_base == "Visual Studio") and \
                generator and "Visual" in generator:
            return {"x86": "Win32",
                    "x86_64": "x64",
                    "armv7": "ARM",
                    "armv8": "ARM64"}.get(arch)
        return None

    def _get_compiler(self, generator):
        compiler = self._conanfile.settings.get_safe("compiler")
        os_ = self._conanfile.settings.get_safe("os")

        compiler_c = compiler_cpp = compiler_rc = None

        # TODO: Check if really necessary now that conanvcvars is used
        if "Ninja" in str(generator) and is_msvc(self._conanfile):
            compiler_c = compiler_cpp = "cl"
        elif os_ == "Windows" and compiler == "clang" and "Visual" not in str(generator):
            compiler_rc = "clang"
            compiler_c = "clang"
            compiler_cpp = "clang++"

        return compiler_c, compiler_cpp, compiler_rc

    def _get_generic_system_name(self):
        os_host = self._conanfile.settings.get_safe("os")
        os_build = self._conanfile.settings_build.get_safe("os")
        arch_host = self._conanfile.settings.get_safe("arch")
        arch_build = self._conanfile.settings_build.get_safe("arch")
        cmake_system_name_map = {"Neutrino": "QNX",
                                 "": "Generic",
                                 None: "Generic"}
        if os_host != os_build:
            return cmake_system_name_map.get(os_host, os_host)
        elif arch_host is not None and arch_host != arch_build:
            if not ((arch_build == "x86_64") and (arch_host == "x86") or
                    (arch_build == "sparcv9") and (arch_host == "sparc") or
                    (arch_build == "ppc64") and (arch_host == "ppc32")):
                return cmake_system_name_map.get(os_host, os_host)

    def _is_apple_cross_building(self):
        os_host = self._conanfile.settings.get_safe("os")
        arch_host = self._conanfile.settings.get_safe("arch")
        arch_build = self._conanfile.settings_build.get_safe("arch")
        return os_host in ('iOS', 'watchOS', 'tvOS') or (
                os_host == 'Macos' and arch_host != arch_build)

    def _get_cross_build(self):
        user_toolchain = self._conanfile.conf.get("tools.cmake.cmaketoolchain:user_toolchain")
        if user_toolchain is not None:
            return None, None, None  # Will be provided by user_toolchain

        system_name = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_name")
        system_version = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_version")
        system_processor = self._conanfile.conf.get("tools.cmake.cmaketoolchain:system_processor")

        if hasattr(self._conanfile, "settings_build"):
            os_host = self._conanfile.settings.get_safe("os")
            arch_host = self._conanfile.settings.get_safe("arch")
            if system_name is None:  # Try to deduce
                _system_version = None
                _system_processor = None
                if self._is_apple_cross_building():
                    # cross-build in Macos also for M1
                    system_name = {'Macos': 'Darwin'}.get(os_host, os_host)
                    #  CMAKE_SYSTEM_VERSION for Apple sets the sdk version, not the os version
                    _system_version = self._conanfile.settings.get_safe("os.sdk_version")
                    _system_processor = to_apple_arch(self._conanfile)
                elif os_host != 'Android':
                    system_name = self._get_generic_system_name()
                    _system_version = self._conanfile.settings.get_safe("os.version")
                    _system_processor = arch_host

                if system_name is not None and system_version is None:
                    system_version = _system_version
                if system_name is not None and system_processor is None:
                    system_processor = _system_processor

        return system_name, system_version, system_processor

    def context(self):
        generator = self._toolchain.generator
        generator_platform = self._get_generator_platform(generator)
        toolset = self._get_toolset(generator)

        compiler, compiler_cpp, compiler_rc = self._get_compiler(generator)

        system_name, system_version, system_processor = self._get_cross_build()

        # This is handled by the tools.apple:sdk_path and CMAKE_OSX_SYSROOT in Apple
        cmake_sysroot = self._conanfile.conf.get("tools.build:sysroot")
        cmake_sysroot = cmake_sysroot.replace("\\", "/") if cmake_sysroot is not None else None

        return {"compiler": compiler,
                "compiler_rc": compiler_rc,
                "compiler_cpp": compiler_cpp,
                "toolset": toolset,
                "generator_platform": generator_platform,
                "cmake_system_name": system_name,
                "cmake_system_version": system_version,
                "cmake_system_processor": system_processor,
                "cmake_sysroot": cmake_sysroot}


class OutputDirsBlock(Block):

    @property
    def template(self):
        if not self._conanfile.package_folder:
            return ""

        return textwrap.dedent("""
           set(CMAKE_INSTALL_PREFIX "{{package_folder}}")
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
        if not self._conanfile.package_folder:
            return {}
        return {"package_folder": self._conanfile.package_folder.replace("\\", "/"),
                "default_bin": self._get_cpp_info_value("bindirs"),
                "default_lib": self._get_cpp_info_value("libdirs"),
                "default_include": self._get_cpp_info_value("includedirs"),
                "default_res": self._get_cpp_info_value("resdirs")}
