import os
import re
import textwrap
from collections import OrderedDict

import six
from jinja2 import Template

from conan.tools._compilers import architecture_flag
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


class Block:
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def get_block(self):
        context = self.context()
        if not context:
            return
        return Template(self.template, trim_blocks=True, lstrip_blocks=True).render(**context)

    def context(self):
        raise NotImplementedError()

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
        if compiler not in ("Visual Studio", "msvc"):
            return

        config_dict = {}
        if os.path.exists(CMakeToolchainBase.filename):
            existing_include = load(CMakeToolchainBase.filename)
            msvc_runtime_value = re.search(r"set\(CMAKE_MSVC_RUNTIME_LIBRARY \"([^)]*)\"\)",
                                           existing_include)
            if msvc_runtime_value:
                capture = msvc_runtime_value.group(1)
                matches = re.findall(r"\$<\$<CONFIG:([A-Za-z]*)>:([A-Za-z]*)>", capture)
                config_dict = dict(matches)

        build_type = settings.get_safe("build_type")  # FIXME: change for configuration
        runtime = settings.get_safe("compiler.runtime")
        if compiler == "Visual Studio":
            config_dict[build_type] = {"MT": "MultiThreaded",
                                       "MTd": "MultiThreadedDebug",
                                       "MD": "MultiThreadedDLL",
                                       "MDd": "MultiThreadedDebugDLL"}[runtime]
        if compiler == "msvc":
            runtime_type = settings.get_safe("compiler.runtime_type")
            rt = "MultiThreadedDebug" if runtime_type == "Debug" else "MultiThreaded"
            if runtime != "static":
                rt += "DLL"
            config_dict[build_type] = rt
        return {"vs_runtimes": config_dict}


class FPicBlock(Block):
    template = textwrap.dedent("""
        message(STATUS "Conan toolchain: Setting CMAKE_POSITION_INDEPENDENT_CODE=ON (options.fPIC)")
        set(CMAKE_POSITION_INDEPENDENT_CODE ON)
        """)

    def context(self):
        fpic = self._conanfile.options.get_safe("fPIC")
        if fpic is None:
            return None
        os_ = self._conanfile.settings.get_safe("os")
        if os_ and "Windows" in os_:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined for Windows")
            return None
        shared = self._conanfile.options.get_safe("shared")
        if shared:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined "
                                        "for a shared library")
            return None
        return {"fpic": fpic}


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
        compiler = self._conanfile.settings.compiler
        lib = glib = None
        if compiler == "apple-clang":
            # In apple-clang 2 only values atm are "libc++" and "libstdc++"
            lib = "-stdlib={}".format(libcxx)
        elif compiler == "clang":
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
        elif compiler == "gcc":
            if libcxx == "libstdc++11":
                glib = "1"
            elif libcxx == "libstdc++":
                glib = "0"
        return {"set_libcxx": lib, "glibcxx": glib}


class SkipRPath(Block):
    template = textwrap.dedent("""
        set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
        # Policy CMP0068
        # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect install_name in OSX
        set(CMAKE_INSTALL_NAME_DIR "")
        """)

    def context(self):
        if self._conanfile.settings.get_safe("os") != "Macos":
            return
        return {"skip_rpath": True}


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
        message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
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
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
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
        max_cpu_count = self._conanfile.conf["tools.cmake.cmaketoolchain"].msvc_parallel_compile

        if max_cpu_count:
            return {"parallel": max_cpu_count}


class BuildTypeBlock(Block):
    template = textwrap.dedent("""
        set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
        """)

    def context(self):
        # build_type (Release, Debug, etc) is only defined for single-config generators
        build_type = build_type or self._conanfile.settings.get_safe("build_type")
        self.build_type = build_type if not is_multi_configuration(self.generator) else None


class CMakeToolchain(object):
    filename = "conan_toolchain.cmake"

    _toolchain_macros_tpl = textwrap.dedent("""
        {% macro iterate_configs(var_config, action) -%}
            {% for it, values in var_config.items() -%}
                {%- set genexpr = namespace(str='') %}
                {%- for conf, value in values -%}
                    {%- set genexpr.str = genexpr.str +
                                          '$<IF:$<CONFIG:' + conf + '>,' + value|string + ',' %}
                    {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
                {%- endfor -%}
                {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}
                {%- endfor -%}
                {% if action=='set' %}
                set({{ it }} {{ genexpr.str }} CACHE STRING
                    "Variable {{ it }} conan-toolchain defined")
                {% elif action=='add_definitions' %}
                add_definitions(-D{{ it }}={{ genexpr.str }})
                {% endif %}
            {%- endfor %}
        {% endmacro %}
        """)

    _base_toolchain_tpl = textwrap.dedent("""
        {% import 'toolchain_macros' as toolchain_macros %}

        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        include_guard()

        # GENERIC
        {% if generator_platform %}set(CMAKE_GENERATOR_PLATFORM "{{ generator_platform }}" CACHE STRING "" FORCE){% endif %}
        {% if toolset %}set(CMAKE_GENERATOR_TOOLSET "{{ toolset }}" CACHE STRING "" FORCE){% endif %}
        {% if compiler %}
        set(CMAKE_C_COMPILER {{ compiler }})
        set(CMAKE_CXX_COMPILER {{ compiler }})
        {% endif %}

        {% for conan_block in conan_pre_blocks %}
        {{ conan_block }}
        {% endfor %}

        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        # We are going to adjust automagically many things as requested by Conan
        #   these are the things done by 'conan_basic_setup()'
        set(CMAKE_EXPORT_NO_PACKAGE_REGISTRY ON)
        {%- if find_package_prefer_config %}
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG {{ find_package_prefer_config }})
        {%- endif %}
        # To support the cmake_find_package generators
        {% if cmake_module_path -%}
        set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
        {%- endif %}
        {% if cmake_prefix_path -%}
        set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
        {%- endif %}

        {% for conan_block in conan_main_blocks %}
        {{ conan_block }}
        {% endfor %}

        set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)

        # Variables
        {% for it, value in variables.items() %}
        set({{ it }} "{{ value }}" CACHE STRING "Variable {{ it }} conan-toolchain defined")
        {% endfor %}
        # Variables  per configuration
        {{ toolchain_macros.iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() %}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}={{ value }})
        {% endfor %}
        # Preprocessor definitions per configuration
        {{ toolchain_macros.iterate_configs(preprocessor_definitions_config,
                                            action='add_definitions') }}
        """)

    def __init__(self, conanfile, generator=None, generator_platform=None, build_type=None,
                 toolset=None):
        self._conanfile = conanfile
        self.variables = Variables()
        self.preprocessor_definitions = Variables()

        # To find the generated cmake_find_package finders
        self.cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self.cmake_module_path = "${CMAKE_BINARY_DIR}"

        self.build_type = None

        self.find_package_prefer_config = "ON"  # assume ON by default if not specified in conf
        prefer_config = conanfile.conf["tools.cmake.cmaketoolchain"].find_package_prefer_config
        if prefer_config is not None and prefer_config.lower() in ("false", "0", "off"):
            self.find_package_prefer_config = "OFF"

        self.conan_pre_blocks = [BuildTypeBlock]
        self.conan_main_blocks = [FPicBlock, SkipRPath, GLibCXXBlock, ArchitectureBlock,
                                  VSRuntimeBlock, CppStdBlock, SharedLibBock, ParallelBlock]

    def _get_template_context_data(self):
        """ Returns dict, the context for the '_template_toolchain'
        """
        self.preprocessor_definitions.quote_preprocessor_strings()

        def process_blocks(blocks):
            result = []
            for b in blocks:
                block = b(self._conanfile).get_block()
                if block:
                    result.append(block)
            return result

        conan_main_blocks = process_blocks(self.conan_main_blocks)
        conan_pre_blocks = process_blocks(self.conan_pre_blocks)

        # base
        ctxt_toolchain = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "build_type": self.build_type,
            "find_package_prefer_config": self.find_package_prefer_config,
            "conan_main_blocks": conan_main_blocks,
            "conan_pre_blocks": conan_pre_blocks
        }
        # generic
        ctxt_toolchain.update({
            "generator_platform": self.generator_platform,
            "toolset": self.toolset,
            "parallel": self.parallel,
            "shared_libs": self._build_shared_libs,
            "compiler": self.compiler,
        })

        return ctxt_toolchain

    def generate(self):
        # Prepare templates to be loaded
        context = self._get_template_context_data()
        content = Template(self.template, trim_blocks=True, lstrip_blocks=True).render(**context)
        save(self.filename, content)
