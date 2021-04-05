import textwrap
from collections import OrderedDict

import six
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


class CMakeToolchainBase(object):
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

        {% block main %}
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
        {% endblock %}

        {% if shared_libs -%}
        message(STATUS "Conan toolchain: Setting BUILD_SHARED_LIBS= {{ shared_libs }}")
        set(BUILD_SHARED_LIBS {{ shared_libs }})
        {%- endif %}

        {% if parallel -%}
        set(CONAN_CXX_FLAGS "${CONAN_CXX_FLAGS} {{ parallel }}")
        set(CONAN_C_FLAGS "${CONAN_C_FLAGS} {{ parallel }}")
        {%- endif %}

        {% if cppstd -%}
        message(STATUS "Conan C++ Standard {{ cppstd }} with extensions {{ cppstd_extensions }}}")
        set(CMAKE_CXX_STANDARD {{ cppstd }})
        set(CMAKE_CXX_EXTENSIONS {{ cppstd_extensions }})
        {%- endif %}

        set(CMAKE_CXX_FLAGS_INIT "${CONAN_CXX_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_C_FLAGS_INIT "${CONAN_C_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_SHARED_LINKER_FLAGS_INIT "${CONAN_SHARED_LINKER_FLAGS}" CACHE STRING "" FORCE)
        set(CMAKE_EXE_LINKER_FLAGS_INIT "${CONAN_EXE_LINKER_FLAGS}" CACHE STRING "" FORCE)

        # Variables
        {% for it, value in variables.items() %}
        set({{ it }} "{{ value }}" CACHE STRING "Variable {{ it }} conan-toolchain defined")
        {%- endfor %}
        # Variables  per configuration
        {{ toolchain_macros.iterate_configs(variables_config, action='set') }}

        # Preprocessor definitions
        {% for it, value in preprocessor_definitions.items() -%}
        # add_compile_definitions only works in cmake >= 3.12
        add_definitions(-D{{ it }}={{ value }})
        {%- endfor %}
        # Preprocessor definitions per configuration
        {{ toolchain_macros.iterate_configs(preprocessor_definitions_config,
                                            action='add_definitions') }}
        """)

    def __init__(self, conanfile, **kwargs):
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

    def _get_templates(self):
        return {
            'toolchain_macros': self._toolchain_macros_tpl,
            'base_toolchain': self._base_toolchain_tpl
        }

    def _get_template_context_data(self):
        """ Returns dict, the context for the '_template_toolchain'
        """
        self.preprocessor_definitions.quote_preprocessor_strings()

        ctxt_toolchain = {
            "variables": self.variables,
            "variables_config": self.variables.configuration_types,
            "preprocessor_definitions": self.preprocessor_definitions,
            "preprocessor_definitions_config": self.preprocessor_definitions.configuration_types,
            "cmake_prefix_path": self.cmake_prefix_path,
            "cmake_module_path": self.cmake_module_path,
            "build_type": self.build_type,
            "find_package_prefer_config": self.find_package_prefer_config,
        }
        return ctxt_toolchain

    def generate(self):
        # Prepare templates to be loaded
        dict_loader = DictLoader(self._get_templates())
        env = Environment(loader=dict_loader)

        ctxt_toolchain = self._get_template_context_data()
        t = env.get_template(self.filename)
        content = t.render(**ctxt_toolchain)
        save(self.filename, content)
