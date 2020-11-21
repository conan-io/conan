import os
import textwrap
from collections import OrderedDict, defaultdict

from jinja2 import DictLoader, Environment

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
            return self._configuration_types.setdefault(config, dict())

    @property
    def configuration_types(self):
        # Reverse index for the configuration_types variables
        ret = defaultdict(list)
        for conf, definitions in self._configuration_types.items():
            for k, v in definitions.items():
                ret[k].append((conf, v))
        return ret


class CMakeToolchainBase(object):
    filename = "conan_toolchain.cmake"
    project_include_filename = "conan_project_include.cmake"

    _toolchain_macros_tpl = textwrap.dedent("""
        {% macro iterate_configs(var_config, action) -%}
            {% for it, values in var_config.items() -%}
                {%- set genexpr = namespace(str='') %}
                {%- for conf, value in values -%}
                    {%- set genexpr.str = genexpr.str +
                                          '$<IF:$<CONFIG:' + conf + '>,"' + value|string + '",' %}
                    {%- if loop.last %}{% set genexpr.str = genexpr.str + '""' -%}{%- endif -%}
                {%- endfor -%}
                {% for i in range(values|count) %}{%- set genexpr.str = genexpr.str + '>' %}{%- endfor -%}
                {% if action=='set' %}
                set({{ it }} {{ genexpr.str }})
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
        if(CONAN_TOOLCHAIN_INCLUDED)
          return()
        endif()
        set(CONAN_TOOLCHAIN_INCLUDED TRUE)

        {% block before_try_compile %}
            {# build_type (Release, Debug, etc) is only defined for single-config generators #}
            {%- if build_type %}
            set(CMAKE_BUILD_TYPE "{{ build_type }}" CACHE STRING "Choose the type of build." FORCE)
            {%- endif %}
        {% endblock %}

        get_property( _CMAKE_IN_TRY_COMPILE GLOBAL PROPERTY IN_TRY_COMPILE )
        if(_CMAKE_IN_TRY_COMPILE)
            message(STATUS "Running toolchain IN_TRY_COMPILE")
            return()
        endif()

        message("Using Conan toolchain through ${CMAKE_TOOLCHAIN_FILE}.")

        {% if conan_project_include_cmake %}
        if(CMAKE_VERSION VERSION_LESS "3.15")
            message(WARNING
                " CMake version less than 3.15 doesn't support CMAKE_PROJECT_INCLUDE variable\\n"
                " used by Conan toolchain to work. In order to get the same behavior you will\\n"
                " need to manually include the generated file after your 'project()' call in the\\n"
                " main CMakeLists.txt file:\\n"
                " \\n"
                "     project(YourProject C CXX)\\n"
                "     include(\\"\\${CMAKE_BINARY_DIR}/conan_project_include.cmake\\")\\n"
                " \\n"
                " This file contains some definitions and extra adjustments that depend on\\n"
                " the build_type and it cannot be done in the toolchain.")
        else()
            # Will be executed after the 'project()' command
            set(CMAKE_PROJECT_INCLUDE "{{ conan_project_include_cmake }}")
        endif()
        {% endif %}

        {% block main %}
            # We are going to adjust automagically many things as requested by Conan
            #   these are the things done by 'conan_basic_setup()'
            set(CMAKE_EXPORT_NO_PACKAGE_REGISTRY ON)
            # To support the cmake_find_package generators
            {% if cmake_module_path -%}
            set(CMAKE_MODULE_PATH {{ cmake_module_path }} ${CMAKE_MODULE_PATH})
            {%- endif %}
            {% if cmake_prefix_path -%}
            set(CMAKE_PREFIX_PATH {{ cmake_prefix_path }} ${CMAKE_PREFIX_PATH})
            {%- endif %}
        {% endblock %}

        # Variables
        {% for it, value in variables.items() %}
        set({{ it }} "{{ value }}")
        {%- endfor %}
        # Variables  per configuration
        {{ toolchain_macros.iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() -%}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}="{{ value }}")
        {%- endfor %}
        # Preprocessor definitions per configuration
        {{ toolchain_macros.iterate_configs(preprocessor_definitions_config, action='add_definitions') }}
        """)

    def __init__(self, conanfile, **kwargs):
        self._conanfile = conanfile
        self.variables = Variables()
        self.preprocessor_definitions = Variables()

        # To find the generated cmake_find_package finders
        self.cmake_prefix_path = "${CMAKE_BINARY_DIR}"
        self.cmake_module_path = "${CMAKE_BINARY_DIR}"

        self.build_type = None

    def _get_templates(self):
        return {
            'toolchain_macros': self._toolchain_macros_tpl,
            'base_toolchain': self._base_toolchain_tpl
        }

    def _get_template_context_data(self):
        """ Returns two dictionaries, the context for the '_template_toolchain' and
            the context for the '_template_project_include' templates.
        """
        ctxt_toolchain = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "build_type": self.build_type,
        }
        return ctxt_toolchain, {}

    def write_toolchain_files(self):
        # Prepare templates to be loaded
        dict_loader = DictLoader(self._get_templates())
        env = Environment(loader=dict_loader)

        ctxt_toolchain, ctxt_project_include = self._get_template_context_data()
        if ctxt_project_include:
            # Make it absolute, wrt to current folder, set by the caller
            conan_project_include_cmake = os.path.abspath(self.project_include_filename)
            conan_project_include_cmake = conan_project_include_cmake.replace("\\", "/")
            t = env.get_template(self.project_include_filename)
            content = t.render(**ctxt_project_include)
            save(conan_project_include_cmake, content)

            ctxt_toolchain.update({'conan_project_include_cmake': conan_project_include_cmake})

        t = env.get_template(self.filename)
        content = t.render(**ctxt_toolchain)
        save(self.filename, content)
