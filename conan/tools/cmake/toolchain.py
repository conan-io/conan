import os
import re
import textwrap
from collections import OrderedDict

import six
from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools._compilers import architecture_flag, use_win_mingw
from conan.tools.build import build_jobs
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.files import save_toolchain_args
from conan.tools.intel import IntelCC
from conan.tools.microsoft import VCVars
from conan.tools.microsoft.visual import vs_ide_version
from conans.errors import ConanException
from conans.util.files import load, save


class Variables(OrderedDict):
    _configuration_types = None  # Needed for py27 to avoid infinite recursion

    def __init__(self):
        super(Variables, self).__init__()
        self._configuration_types = {}

    def __getattribute__(self, config):
        try:
            return super(Variables, self).__getattribute__(config)
        except AttributeError:
            return self._configuration_types.setdefault(config, OrderedDict())

    @property
    def configuration_types(self):
        # Reverse index for the configuration_types variables
        ret = OrderedDict()
        for conf, definitions in self._configuration_types.items():
            for k, v in definitions.items():
                ret.setdefault(k, []).append((conf, v))
        return ret

    def quote_preprocessor_strings(self):
        for key, var in self.items():
            if isinstance(var, six.string_types):
                self[key] = '"{}"'.format(var)
        for config, data in self._configuration_types.items():
            for key, var in data.items():
                if isinstance(var, six.string_types):
                    data[key] = '"{}"'.format(var)


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
        set(CMAKE_MSVC_RUNTIME_LIBRARY "{{ genexpr.str }}")
        """)

    def context(self):
        # Parsing existing toolchain file to get existing configured runtimes
        settings = self._conanfile.settings
        compiler = settings.get_safe("compiler")
        if compiler not in ("Visual Studio", "msvc", "intel-cc"):
            return

        config_dict = {}
        if os.path.exists(CMakeToolchain.filename):
            existing_include = load(CMakeToolchain.filename)
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
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ set_libcxx }}")
        {% endif %}
        {% if glibcxx %}
        add_definitions(-D_GLIBCXX_USE_CXX11_ABI={{ glibcxx }})
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
            elif libcxx == "libstdc++11" and self._conanfile.conf["tools.gnu:define_libcxx11_abi"]:
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
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ arch_flag }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ arch_flag }}")
        set(CONAN_SHARED_LINKER_FLAGS "${CONAN_SHARED_LINKER_FLAGS} {{ arch_flag }}")
        set(CONAN_EXE_LINKER_FLAGS "${CONAN_EXE_LINKER_FLAGS} {{ arch_flag }}")
        """)

    def context(self):
        arch_flag = architecture_flag(self._conanfile.settings)
        if not arch_flag:
            return
        return {"arch_flag": arch_flag}


class CppStdBlock(Block):
    template = textwrap.dedent("""
        message(STATUS "Conan toolchain: C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
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
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} /MP{{ parallel }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} /MP{{ parallel }}")
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
        set(ANDROID_PLATFORM {{ ANDROID_PLATFORM }})
        set(ANDROID_STL {{ ANDROID_STL }})
        set(ANDROID_ABI {{ ANDROID_ABI }})
        include({{ ANDROID_NDK_PATH }}/build/cmake/android.toolchain.cmake)
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
        libcxx_str = str(self._conanfile.settings.compiler.libcxx)

        android_ndk_path = self._conanfile.conf["tools.android:ndk_path"]
        if not android_ndk_path:
            raise ConanException('CMakeToolchain needs tools.android:ndk_path configuration defined')
        android_ndk_path = android_ndk_path.replace("\\", "/")

        ctxt_toolchain = {
            'ANDROID_PLATFORM': self._conanfile.settings.os.api_level,
            'ANDROID_ABI': android_abi,
            'ANDROID_STL': libcxx_str,
            'ANDROID_NDK_PATH': android_ndk_path,
        }
        return ctxt_toolchain


class AppleSystemBlock(Block):
    template = textwrap.dedent("""
        {% if CMAKE_SYSTEM_NAME is defined %}
        set(CMAKE_SYSTEM_NAME {{ CMAKE_SYSTEM_NAME }})
        {% endif %}
        {% if CMAKE_SYSTEM_VERSION is defined %}
        set(CMAKE_SYSTEM_VERSION {{ CMAKE_SYSTEM_VERSION }})
        {% endif %}
        # Set the architectures for which to build.
        set(CMAKE_OSX_ARCHITECTURES {{ CMAKE_OSX_ARCHITECTURES }} CACHE STRING "" FORCE)
        # Setting CMAKE_OSX_SYSROOT SDK, when using Xcode generator the name is enough
        # but full path is necessary for others
        set(CMAKE_OSX_SYSROOT {{ CMAKE_OSX_SYSROOT }} CACHE STRING "" FORCE)
        {% if CMAKE_OSX_DEPLOYMENT_TARGET is defined %}
        # Setting CMAKE_OSX_DEPLOYMENT_TARGET if "os.version" is defined by the used conan profile
        set(CMAKE_OSX_DEPLOYMENT_TARGET "{{ CMAKE_OSX_DEPLOYMENT_TARGET }}" CACHE STRING "")
        {% endif %}
        """)

    def _get_architecture(self):
        # check valid combinations of architecture - os ?
        # for iOS a FAT library valid for simulator and device
        # can be generated if multiple archs are specified:
        # "-DCMAKE_OSX_ARCHITECTURES=armv7;armv7s;arm64;i386;x86_64"
        arch = self._conanfile.settings.get_safe("arch")
        return {"x86": "i386",
                "x86_64": "x86_64",
                "armv8": "arm64",
                "armv8_32": "arm64_32"}.get(arch, arch)

    # TODO: refactor, comes from conans.client.tools.apple.py
    def _apple_sdk_name(self):
        """returns proper SDK name suitable for OS and architecture
        we're building for (considering simulators)"""
        arch = self._conanfile.settings.get_safe('arch')
        os_ = self._conanfile.settings.get_safe('os')
        if arch.startswith('x86'):
            return {'Macos': 'macosx',
                    'iOS': 'iphonesimulator',
                    'watchOS': 'watchsimulator',
                    'tvOS': 'appletvsimulator'}.get(os_)
        else:
            return {'Macos': 'macosx',
                    'iOS': 'iphoneos',
                    'watchOS': 'watchos',
                    'tvOS': 'appletvos'}.get(os_)

    def context(self):
        os_ = self._conanfile.settings.get_safe("os")
        if os_ not in ['Macos', 'iOS', 'watchOS', 'tvOS']:
            return None

        host_architecture = self._get_architecture()
        host_os_version = self._conanfile.settings.get_safe("os.version")
        host_sdk_name = self._apple_sdk_name()

        ctxt_toolchain = {}
        if host_sdk_name:
            ctxt_toolchain["CMAKE_OSX_SYSROOT"] = host_sdk_name
        if host_architecture:
            ctxt_toolchain["CMAKE_OSX_ARCHITECTURES"] = host_architecture

        if os_ in ('iOS', "watchOS", "tvOS"):
            ctxt_toolchain["CMAKE_SYSTEM_NAME"] = os_
            ctxt_toolchain["CMAKE_SYSTEM_VERSION"] = host_os_version

        if host_os_version:
            # https://cmake.org/cmake/help/latest/variable/CMAKE_OSX_DEPLOYMENT_TARGET.html
            # Despite the OSX part in the variable name(s) they apply also to other SDKs than
            # macOS like iOS, tvOS, or watchOS.
            ctxt_toolchain["CMAKE_OSX_DEPLOYMENT_TARGET"] = host_os_version

        return ctxt_toolchain


class FindConfigFiles(Block):
    template = textwrap.dedent("""
        {% if find_package_prefer_config %}
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG {{ find_package_prefer_config }})
        {% endif %}
        # To support the generators based on find_package()
        {% if cmake_module_path %}
        set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
        {% endif %}
        {% if cmake_prefix_path %}
        set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
        {% endif %}
        {% if android_prefix_path %}
        set(CMAKE_FIND_ROOT_PATH {{ android_prefix_path }} ${CMAKE_FIND_ROOT_PATH})
        {% endif %}

        # To support cross building to iOS, watchOS and tvOS where CMake looks for config files
        # only in the system frameworks unless you declare the XXX_DIR variables
        {% if cross_ios %}
            set(CMAKE_FIND_ROOT_PATH_MODE_PACKAGE BOTH)
        {% endif %}
        """)

    def context(self):
        # To find the generated cmake_find_package finders
        # TODO: Change this for parameterized output location of CMakeDeps
        find_package_prefer_config = "ON"  # assume ON by default if not specified in conf
        prefer_config = self._conanfile.conf["tools.cmake.cmaketoolchain:find_package_prefer_config"]
        if prefer_config is not None and prefer_config.lower() in ("false", "0", "off"):
            find_package_prefer_config = "OFF"

        os_ = self._conanfile.settings.get_safe("os")
        android_prefix = "${CMAKE_CURRENT_LIST_DIR}" if os_ == "Android" else None

        host_req = self._conanfile.dependencies.host.values()
        cross_ios = os_ in ('iOS', "watchOS", "tvOS")

        # Read the buildirs
        build_paths = []
        for req in host_req:
            cppinfo = req.cpp_info.aggregated_components()
            build_paths.extend([os.path.join(req.package_folder,
                                       p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"'))
                                for p in cppinfo.builddirs])

        if self._toolchain.find_builddirs:
            build_paths = " ".join(['"{}"'.format(b.replace('\\', '/')
                                                   .replace('$', '\\$')
                                                   .replace('"', '\\"')) for b in build_paths])
        else:
            build_paths = ""

        return {"find_package_prefer_config": find_package_prefer_config,
                "cmake_prefix_path": "${CMAKE_CURRENT_LIST_DIR} " + build_paths,
                "cmake_module_path": "${CMAKE_CURRENT_LIST_DIR} " + build_paths,
                "android_prefix_path": android_prefix,
                "cross_ios": cross_ios,
                "generators_folder": "${CMAKE_CURRENT_LIST_DIR}"}


class UserToolchain(Block):
    template = textwrap.dedent("""
        {% if user_toolchain %}
        include("{{user_toolchain}}")
        {% endif %}
        """)

    user_toolchain = None

    def context(self):
        # This is global [conf] injection of extra toolchain files
        user_toolchain = self._conanfile.conf["tools.cmake.cmaketoolchain:user_toolchain"]
        user_toolchain = user_toolchain or self.user_toolchain
        if user_toolchain:
            user_toolchain = user_toolchain.replace("\\", "/")
        return {"user_toolchain": user_toolchain}


class CMakeFlagsInitBlock(Block):
    template = textwrap.dedent("""
        set(CMAKE_CXX_FLAGS_INIT "${CMAKE_CXX_FLAGS_INIT} ${CONAN_CXX_FLAGS}")
        set(CMAKE_C_FLAGS_INIT "${CMAKE_C_FLAGS_INIT} ${CONAN_C_FLAGS}")
        set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CMAKE_SHARED_LINKER_FLAGS_INIT} ${CONAN_SHARED_LINKER_FLAGS}")
        set(CMAKE_EXE_LINKER_FLAGS_INIT "${CMAKE_EXE_LINKER_FLAGS_INIT} ${CONAN_EXE_LINKER_FLAGS}")
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
        {% if cmake_system_name %}
        # Cross building
        set(CMAKE_SYSTEM_NAME {{ cmake_system_name }})
        {% endif %}
        {% if cmake_system_version %}
        # Cross building
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
        set(CMAKE_C_COMPILER {{ compiler }})
        set(CMAKE_CXX_COMPILER {{ compiler }})
        {% endif %}
        {% if build_type %}
        set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
        {% endif %}
        """)

    def _get_toolset(self, generator):
        if generator is None or ("Visual" not in generator and "Xcode" not in generator):
            return None
        settings = self._conanfile.settings
        compiler = settings.get_safe("compiler")
        compiler_base = settings.get_safe("compiler.base")
        if compiler == "Visual Studio":
            subs_toolset = settings.get_safe("compiler.toolset")
            if subs_toolset:
                return subs_toolset
        elif compiler == "intel" and compiler_base == "Visual Studio" and "Visual" in generator:
            # TODO: This intel toolset needs to be validated too
            compiler_version = settings.get_safe("compiler.version")
            if compiler_version:
                compiler_version = compiler_version if "." in compiler_version else \
                    "%s.0" % compiler_version
                return "Intel C++ Compiler " + compiler_version
        elif compiler == "intel-cc":
            return IntelCC(self._conanfile).ms_toolset
        elif compiler == "msvc":
            compiler_version = str(settings.compiler.version)
            compiler_update = str(settings.compiler.update)
            if compiler_update != "None":  # It is full one(19.28), not generic 19.2X
                # The equivalent of compiler 19.26 is toolset 14.26
                return "version=14.{}{}".format(compiler_version[-1], compiler_update)
            else:
                return "v14{}".format(compiler_version[-1])
        elif compiler == "clang":
            if generator and "Visual" in generator:
                if "Visual Studio 16" in generator:
                    return "ClangCL"
                else:
                    raise ConanException("CMakeToolchain compiler=clang only supported VS 16")
        return None

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

    def _get_cross_build(self):
        user_toolchain = self._conanfile.conf["tools.cmake.cmaketoolchain:user_toolchain"]
        if user_toolchain is not None:
            return None, None, None  # Will be provided by user_toolchain

        system_name = self._conanfile.conf["tools.cmake.cmaketoolchain:system_name"]
        system_version = self._conanfile.conf["tools.cmake.cmaketoolchain:system_version"]
        system_processor = self._conanfile.conf["tools.cmake.cmaketoolchain:system_processor"]

        settings = self._conanfile.settings
        if hasattr(self._conanfile, "settings_build"):
            os_ = settings.get_safe("os")
            arch = settings.get_safe("arch")
            settings_build = self._conanfile.settings_build
            os_build = settings_build.get_safe("os")
            arch_build = settings_build.get_safe("arch")

            if system_name is None:  # Try to deduce
                # Handled by AppleBlock, or AndroidBlock, not here
                if os_ not in ('Macos', 'iOS', 'watchOS', 'tvOS', 'Android'):
                    cmake_system_name_map = {"Neutrino": "QNX",
                                             "": "Generic",
                                             None: "Generic"}
                    if os_ != os_build:
                        system_name = cmake_system_name_map.get(os_, os_)
                    elif arch is not None and arch != arch_build:
                        if not ((arch_build == "x86_64") and (arch == "x86") or
                                (arch_build == "sparcv9") and (arch == "sparc") or
                                (arch_build == "ppc64") and (arch == "ppc32")):
                            system_name = cmake_system_name_map.get(os_, os_)

            if system_name is not None and system_version is None:
                system_version = settings.get_safe("os.version")

            if system_name is not None and system_processor is None:
                if arch != arch_build:
                    system_processor = arch

        return system_name, system_version, system_processor

    def context(self):
        # build_type (Release, Debug, etc) is only defined for single-config generators
        generator = self._toolchain.generator
        generator_platform = self._get_generator_platform(generator)
        toolset = self._get_toolset(generator)
        compiler = self._conanfile.settings.get_safe("compiler")
        # TODO: Check if really necessary now that conanvcvars is used
        if (generator is not None and "Ninja" in generator
                and (compiler is not None and "Visual" in compiler or compiler == "msvc")):
            compiler = "cl"
        else:
            compiler = None  # compiler defined by default

        build_type = self._conanfile.settings.get_safe("build_type")
        build_type = build_type if not is_multi_configuration(generator) else None

        system_name, system_version, system_processor = self._get_cross_build()

        return {"compiler": compiler,
                "toolset": toolset,
                "generator_platform": generator_platform,
                "build_type": build_type,
                "cmake_system_name": system_name,
                "cmake_system_version": system_version,
                "cmake_system_processor": system_processor}


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


class CMakeToolchain(object):
    filename = "conan_toolchain.cmake"

    _template = textwrap.dedent("""
        {% macro iterate_configs(var_config, action) %}
            {% for it, values in var_config.items() %}
                {% set genexpr = namespace(str='') %}
                {% for conf, value in values -%}
                    {% set genexpr.str = genexpr.str +
                                          '$<IF:$<CONFIG:' + conf + '>,' + value|string + ',' %}
                    {% if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
                {% endfor %}
                {% for i in range(values|count) %}{% set genexpr.str = genexpr.str + '>' %}
                {% endfor %}
                {% if action=='set' %}
                set({{ it }} {{ genexpr.str }} CACHE STRING
                    "Variable {{ it }} conan-toolchain defined")
                {% elif action=='add_definitions' %}
                add_definitions(-D{{ it }}={{ genexpr.str }})
                {% endif %}
            {% endfor %}
        {% endmacro %}

        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        include_guard()

        if(CMAKE_TOOLCHAIN_FILE)
            message("Using Conan toolchain: ${CMAKE_TOOLCHAIN_FILE}.")
        endif()

        {% for conan_block in conan_blocks %}
        {{ conan_block }}
        {% endfor %}

        # Variables
        {% for it, value in variables.items() %}
        set({{ it }} {{ value|cmake_value }} CACHE STRING "Variable {{ it }} conan-toolchain defined")
        {% endfor %}
        # Variables  per configuration
        {{ iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() %}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}={{ value }})
        {% endfor %}
        # Preprocessor definitions per configuration
        {{ iterate_configs(preprocessor_definitions_config, action='add_definitions') }}
        """)

    def __init__(self, conanfile, generator=None, namespace=None):
        self._conanfile = conanfile
        self.generator = self._get_generator(generator)
        self._namespace = namespace
        self.variables = Variables()
        self.preprocessor_definitions = Variables()

        self.blocks = ToolchainBlocks(self._conanfile, self,
                                      [("user_toolchain", UserToolchain),
                                       ("generic_system", GenericSystemBlock),
                                       ("android_system", AndroidSystemBlock),
                                       ("apple_system", AppleSystemBlock),
                                       ("fpic", FPicBlock),
                                       ("arch_flags", ArchitectureBlock),
                                       ("libcxx", GLibCXXBlock),
                                       ("vs_runtime", VSRuntimeBlock),
                                       ("cppstd", CppStdBlock),
                                       ("parallel", ParallelBlock),
                                       ("cmake_flags_init", CMakeFlagsInitBlock),
                                       ("try_compile", TryCompileBlock),
                                       ("find_paths", FindConfigFiles),
                                       ("rpath", SkipRPath),
                                       ("shared", SharedLibBock)])

        # Set the CMAKE_MODULE_PATH and CMAKE_PREFIX_PATH to the deps .builddirs
        self.find_builddirs = True

        check_using_build_profile(self._conanfile)

    def _context(self):
        """ Returns dict, the context for the template
        """
        self.preprocessor_definitions.quote_preprocessor_strings()
        blocks = self.blocks.process_blocks()
        ctxt_toolchain = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "conan_blocks": blocks
        }

        return ctxt_toolchain

    @property
    def content(self):
        context = self._context()
        content = Template(self._template, trim_blocks=True, lstrip_blocks=True).render(**context)
        return content

    def generate(self):
        toolchain_file = self._conanfile.conf["tools.cmake.cmaketoolchain:toolchain_file"]
        if toolchain_file is None:  # The main toolchain file generated only if user dont define
            save(self.filename, self.content)
        # If we're using Intel oneAPI, we need to generate the environment file and run it
        if self._conanfile.settings.get_safe("compiler") == "intel-cc":
            IntelCC(self._conanfile).generate()
        # Generators like Ninja or NMake requires an active vcvars
        elif self.generator is not None and "Visual" not in self.generator:
            VCVars(self._conanfile).generate()
        self._writebuild(toolchain_file)

    def _writebuild(self, toolchain_file):
        result = {}
        # TODO: Lets do it compatible with presets soon
        if self.generator is not None:
            result["cmake_generator"] = self.generator

        result["cmake_toolchain_file"] = toolchain_file or self.filename

        if result:
            save_toolchain_args(result, namespace=self._namespace)

    def _get_generator(self, recipe_generator):
        # Returns the name of the generator to be used by CMake
        conanfile = self._conanfile

        # Downstream consumer always higher priority
        generator_conf = conanfile.conf["tools.cmake.cmaketoolchain:generator"]
        if generator_conf:
            return generator_conf

        # second priority: the recipe one:
        if recipe_generator:
            return recipe_generator

        # if not defined, deduce automatically the default one
        compiler = conanfile.settings.get_safe("compiler")
        compiler_version = conanfile.settings.get_safe("compiler.version")

        cmake_years = {'8': '8 2005',
                       '9': '9 2008',
                       '10': '10 2010',
                       '11': '11 2012',
                       '12': '12 2013',
                       '14': '14 2015',
                       '15': '15 2017',
                       '16': '16 2019',
                       '17': '17 2022'}

        if compiler == "msvc":
            if compiler_version is None:
                raise ConanException("compiler.version must be defined")
            vs_version = vs_ide_version(self._conanfile)
            return "Visual Studio %s" % cmake_years[vs_version]

        compiler_base = conanfile.settings.get_safe("compiler.base")
        compiler_base_version = conanfile.settings.get_safe("compiler.base.version")

        if compiler == "Visual Studio" or compiler_base == "Visual Studio":
            version = compiler_base_version or compiler_version
            major_version = version.split('.', 1)[0]
            base = "Visual Studio %s" % cmake_years[major_version]
            return base

        if use_win_mingw(conanfile):
            return "MinGW Makefiles"

        return "Unix Makefiles"
