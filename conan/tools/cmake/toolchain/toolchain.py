import os
import textwrap
from collections import OrderedDict

import six
from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools._compilers import use_win_mingw
from conan.tools.cmake.presets import write_cmake_presets
from conan.tools.cmake.toolchain import CONAN_TOOLCHAIN_FILENAME
from conan.tools.cmake.toolchain.blocks import ToolchainBlocks, UserToolchain, GenericSystemBlock, \
    AndroidSystemBlock, AppleSystemBlock, FPicBlock, ArchitectureBlock, GLibCXXBlock, VSRuntimeBlock, \
    CppStdBlock, ParallelBlock, CMakeFlagsInitBlock, TryCompileBlock, FindFiles, SkipRPath, \
    SharedLibBock, OutputDirsBlock, ExtraFlagsBlock
from conan.tools.intel import IntelCC
from conan.tools.microsoft import VCVars
from conan.tools.microsoft.visual import vs_ide_version
from conans.errors import ConanException
from conans.util.files import save


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
                self[key] = str(var).replace('"', '\\"')
        for config, data in self._configuration_types.items():
            for key, var in data.items():
                if isinstance(var, six.string_types):
                    data[key] = str(var).replace('"', '\\"')


class CMakeToolchain(object):

    filename = CONAN_TOOLCHAIN_FILENAME

    _template = textwrap.dedent("""
        {% macro iterate_configs(var_config, action) %}
            {% for it, values in var_config.items() %}
                {% set genexpr = namespace(str='') %}
                {% for conf, value in values -%}
                set(CONAN_DEF_{{ conf }}{{ it }} "{{ value }}")
                {% endfor %}
                {% for conf, value in values -%}
                    {% set genexpr.str = genexpr.str +
                                          '$<IF:$<CONFIG:' + conf + '>,${CONAN_DEF_' + conf|string + it|string + '},' %}
                    {% if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
                {% endfor %}
                {% for i in range(values|count) %}{% set genexpr.str = genexpr.str + '>' %}
                {% endfor %}
                {% if action=='set' %}
                set({{ it }} {{ genexpr.str }} CACHE STRING
                    "Variable {{ it }} conan-toolchain defined")
                {% elif action=='add_compile_definitions' -%}
                add_compile_definitions({{ it }}={{ genexpr.str }})
                {% endif %}
            {% endfor %}
        {% endmacro %}

        # Conan automatically generated toolchain file
        # DO NOT EDIT MANUALLY, it will be overwritten

        # Avoid including toolchain file several times (bad if appending to variables like
        #   CMAKE_CXX_FLAGS. See https://github.com/android/ndk/issues/323
        include_guard()

        message(STATUS "Using Conan toolchain: ${CMAKE_CURRENT_LIST_FILE}")

        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeToolchain' generator only works with CMake >= 3.15")
        endif()

        {% for conan_block in conan_blocks %}
        {{ conan_block }}
        {% endfor %}

        # Variables
        {% for it, value in variables.items() %}
        {% if value is boolean %}
        set({{ it }} {{ value|cmake_value }} CACHE BOOL "Variable {{ it }} conan-toolchain defined")
        {% else %}
        set({{ it }} {{ value|cmake_value }} CACHE STRING "Variable {{ it }} conan-toolchain defined")
        {% endif %}
        {% endfor %}
        # Variables  per configuration
        {{ iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() %}
        add_compile_definitions("{{ it }}={{ value }}")
        {% endfor %}
        # Preprocessor definitions per configuration
        {{ iterate_configs(preprocessor_definitions_config, action='add_compile_definitions') }}
        """)

    def __init__(self, conanfile, generator=None):
        self._conanfile = conanfile
        self.generator = self._get_generator(generator)
        self.variables = Variables()
        # This doesn't support multi-config, they go to the same configPreset common in multi-config
        self.cache_variables = {}
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
                                       ("extra_flags", ExtraFlagsBlock),
                                       ("cmake_flags_init", CMakeFlagsInitBlock),
                                       ("try_compile", TryCompileBlock),
                                       ("find_paths", FindFiles),
                                       ("rpath", SkipRPath),
                                       ("shared", SharedLibBock),
                                       ("output_dirs", OutputDirsBlock)])

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
        toolchain_file = self._conanfile.conf.get("tools.cmake.cmaketoolchain:toolchain_file")
        if toolchain_file is None:  # The main toolchain file generated only if user dont define
            save(os.path.join(self._conanfile.generators_folder, self.filename), self.content)
        # If we're using Intel oneAPI, we need to generate the environment file and run it
        if self._conanfile.settings.get_safe("compiler") == "intel-cc":
            IntelCC(self._conanfile).generate()
        # Generators like Ninja or NMake requires an active vcvars
        elif self.generator is not None and "Visual" not in self.generator:
            VCVars(self._conanfile).generate()
        toolchain = os.path.abspath(os.path.join(self._conanfile.generators_folder,
                                                 toolchain_file or self.filename))
        cache_variables = {}
        for name, value in self.cache_variables.items():
            if isinstance(value, bool):
                cache_variables[name] = "ON" if value else "OFF"
            else:
                cache_variables[name] = value

        write_cmake_presets(self._conanfile, toolchain, self.generator, cache_variables)

    def _get_generator(self, recipe_generator):
        # Returns the name of the generator to be used by CMake
        conanfile = self._conanfile

        # Downstream consumer always higher priority
        generator_conf = conanfile.conf.get("tools.cmake.cmaketoolchain:generator")
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
