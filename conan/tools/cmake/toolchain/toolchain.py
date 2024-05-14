import os
import textwrap
from collections import OrderedDict

from jinja2 import Template

from conan.api.output import ConanOutput
from conan.internal import check_duplicated_generator
from conan.tools.build import use_win_mingw
from conan.tools.cmake.presets import write_cmake_presets
from conan.tools.cmake.toolchain import CONAN_TOOLCHAIN_FILENAME
from conan.tools.cmake.toolchain.blocks import ToolchainBlocks, UserToolchain, GenericSystemBlock, \
    AndroidSystemBlock, AppleSystemBlock, FPicBlock, ArchitectureBlock, GLibCXXBlock, VSRuntimeBlock, \
    CppStdBlock, ParallelBlock, CMakeFlagsInitBlock, TryCompileBlock, FindFiles, PkgConfigBlock, \
    SkipRPath, SharedLibBock, OutputDirsBlock, ExtraFlagsBlock, CompilersBlock, LinkerScriptsBlock, \
    VSDebuggerEnvironment
from conan.tools.cmake.utils import is_multi_configuration
from conan.tools.env import VirtualBuildEnv, VirtualRunEnv
from conan.tools.intel import IntelCC
from conan.tools.microsoft import VCVars
from conan.tools.microsoft.visual import vs_ide_version
from conans.client.generators import relativize_generated_file
from conan.errors import ConanException
from conans.model.options import _PackageOption
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
            if isinstance(var, str):
                self[key] = str(var).replace('"', '\\"')
        for config, data in self._configuration_types.items():
            for key, var in data.items():
                if isinstance(var, str):
                    data[key] = str(var).replace('"', '\\"')


class CMakeToolchain(object):

    filename = CONAN_TOOLCHAIN_FILENAME

    # TODO: Clean this macro, do it explicitly for variables
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
                set({{ it }} {{ genexpr.str }} CACHE STRING
                    "Variable {{ it }} conan-toolchain defined")
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
        set({{ it }} {{ "ON" if value else "OFF"}} CACHE BOOL "Variable {{ it }} conan-toolchain defined")
        {% else %}
        set({{ it }} "{{ value }}" CACHE STRING "Variable {{ it }} conan-toolchain defined")
        {% endif %}
        {% endfor %}
        # Variables  per configuration
        {{ iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() %}
        {% if value is none %}
        add_compile_definitions("{{ it }}")
        {% else %}
        add_compile_definitions("{{ it }}={{ value }}")
        {% endif %}
        {% endfor %}
        # Preprocessor definitions per configuration
        {% for name, values in preprocessor_definitions_config.items() %}
        {%- for (conf, value) in values %}
        {% if value is none %}
        set(CONAN_DEF_{{conf}}_{{name}} "{{name}}")
        {% else %}
        set(CONAN_DEF_{{conf}}_{{name}} "{{name}}={{value}}")
        {% endif %}
        {% endfor %}
        add_compile_definitions(
        {%- for (conf, value) in values %}
        $<$<CONFIG:{{conf}}>:${CONAN_DEF_{{conf}}_{{name}}}>
        {%- endfor -%})
        {% endfor %}


        if(CMAKE_POLICY_DEFAULT_CMP0091)  # Avoid unused and not-initialized warnings
        endif()
        """)

    def __init__(self, conanfile, generator=None):
        self._conanfile = conanfile
        self.generator = self._get_generator(generator)
        self.variables = Variables()
        # This doesn't support multi-config, they go to the same configPreset common in multi-config
        self.cache_variables = {}
        self.preprocessor_definitions = Variables()

        self.extra_cxxflags = []
        self.extra_cflags = []
        self.extra_sharedlinkflags = []
        self.extra_exelinkflags = []

        self.blocks = ToolchainBlocks(self._conanfile, self,
                                      [("user_toolchain", UserToolchain),
                                       ("generic_system", GenericSystemBlock),
                                       ("compilers", CompilersBlock),
                                       ("android_system", AndroidSystemBlock),
                                       ("apple_system", AppleSystemBlock),
                                       ("fpic", FPicBlock),
                                       ("arch_flags", ArchitectureBlock),
                                       ("linker_scripts", LinkerScriptsBlock),
                                       ("libcxx", GLibCXXBlock),
                                       ("vs_runtime", VSRuntimeBlock),
                                       ("vs_debugger_environment", VSDebuggerEnvironment),
                                       ("cppstd", CppStdBlock),
                                       ("parallel", ParallelBlock),
                                       ("extra_flags", ExtraFlagsBlock),
                                       ("cmake_flags_init", CMakeFlagsInitBlock),
                                       ("try_compile", TryCompileBlock),
                                       ("find_paths", FindFiles),
                                       ("pkg_config", PkgConfigBlock),
                                       ("rpath", SkipRPath),
                                       ("shared", SharedLibBock),
                                       ("output_dirs", OutputDirsBlock)])

        # Set the CMAKE_MODULE_PATH and CMAKE_PREFIX_PATH to the deps .builddirs
        self.find_builddirs = True
        self.user_presets_path = "CMakeUserPresets.json"
        self.presets_prefix = "conan"
        self.presets_build_environment = None
        self.presets_run_environment = None

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
        content = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                           keep_trailing_newline=True).render(**context)
        content = relativize_generated_file(content, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
        return content

    @property
    def is_multi_configuration(self):
        return is_multi_configuration(self.generator)

    def _find_cmake_exe(self):
        for req in self._conanfile.dependencies.direct_build.values():
            if req.ref.name == "cmake":
                for bindir in req.cpp_info.bindirs:
                    cmake_path = os.path.join(bindir, "cmake")
                    cmake_exe_path = os.path.join(bindir, "cmake.exe")

                    if os.path.exists(cmake_path):
                        return cmake_path
                    elif os.path.exists(cmake_exe_path):
                        return cmake_exe_path

    def generate(self):
        """
          This method will save the generated files to the conanfile.generators_folder
        """
        check_duplicated_generator(self, self._conanfile)
        toolchain_file = self._conanfile.conf.get("tools.cmake.cmaketoolchain:toolchain_file")
        if toolchain_file is None:  # The main toolchain file generated only if user dont define
            toolchain_file = self.filename
            save(os.path.join(self._conanfile.generators_folder, toolchain_file), self.content)
            ConanOutput(str(self._conanfile)).info(f"CMakeToolchain generated: {toolchain_file}")
        # If we're using Intel oneAPI, we need to generate the environment file and run it
        if self._conanfile.settings.get_safe("compiler") == "intel-cc":
            IntelCC(self._conanfile).generate()
        # Generators like Ninja or NMake requires an active vcvars
        elif self.generator is not None and "Visual" not in self.generator:
            VCVars(self._conanfile).generate()

        cache_variables = {}
        for name, value in self.cache_variables.items():
            if isinstance(value, bool):
                cache_variables[name] = "ON" if value else "OFF"
            elif isinstance(value, _PackageOption):
                if str(value).lower() in ["true", "false", "none"]:
                    cache_variables[name] = "ON" if bool(value) else "OFF"
                elif str(value).isdigit():
                    cache_variables[name] = int(value)
                else:
                    cache_variables[name] = str(value)
            else:
                cache_variables[name] = value

        buildenv, runenv, cmake_executable = None, None, None

        if self._conanfile.conf.get("tools.cmake.cmaketoolchain:presets_environment", default="",
                                    check_type=str, choices=("disabled", "")) != "disabled":

            build_env = self.presets_build_environment.vars(self._conanfile) if self.presets_build_environment else VirtualBuildEnv(self._conanfile, auto_generate=True).vars()
            run_env = self.presets_run_environment.vars(self._conanfile) if self.presets_run_environment else VirtualRunEnv(self._conanfile, auto_generate=True).vars()

            buildenv = {name: value for name, value in
                        build_env.items(variable_reference="$penv{{{name}}}")}
            runenv = {name: value for name, value in
                      run_env.items(variable_reference="$penv{{{name}}}")}

            cmake_executable = self._conanfile.conf.get("tools.cmake:cmake_program", None) or self._find_cmake_exe()

        write_cmake_presets(self._conanfile, toolchain_file, self.generator, cache_variables,
                            self.user_presets_path, self.presets_prefix, buildenv, runenv,
                            cmake_executable)

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

        if use_win_mingw(conanfile):
            return "MinGW Makefiles"

        return "Unix Makefiles"
