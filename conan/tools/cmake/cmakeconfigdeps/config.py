import textwrap

import jinja2
from jinja2 import Template


class ConfigTemplate2:
    """
    FooConfig.cmake / foo-config.cmake

    Thin Jinja renderer. Filename and context are built by CMakeConfigDeps.
    """
    def __init__(self, filename, context):
        self._filename = filename
        self._context = context

    @property
    def filename(self):
        return self._filename

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def _template(self):
        return textwrap.dedent("""\
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ targets_include_file }})

        get_property(isMultiConfig GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
        if(NOT isMultiConfig AND NOT CMAKE_BUILD_TYPE)
           message(FATAL_ERROR "Please, set the CMAKE_BUILD_TYPE variable when calling to CMake "
                               "adding the '-DCMAKE_BUILD_TYPE=<build_type>' argument.")
        endif()

        {% if components %}
        set({{filename}}_PACKAGE_PROVIDED_COMPONENTS {{components}})
        foreach(comp {%raw%}${{%endraw%}{{filename}}_FIND_COMPONENTS})
          if(NOT ${comp} IN_LIST {{filename}}_PACKAGE_PROVIDED_COMPONENTS)
            if({%raw%}${{%endraw%}{{filename}}_FIND_REQUIRED_${comp}})
              message(STATUS "Conan: Error: '{{pkg_name}}' required COMPONENT '${comp}' not found")
              set({{filename}}_FOUND FALSE)
            endif()
          endif()
        endforeach()
        {% endif %}

        ################# Global variables for try compile and legacy ##############
        {% for prefix in additional_variables_prefixes %}
        set({{ prefix }}_VERSION_STRING "{{ version }}")
        {% if include_dirs is not none %}
        set({{ prefix }}_INCLUDE_DIRS "{{ include_dirs }}" )
        set({{ prefix }}_INCLUDE_DIR "{{ include_dirs }}" )
        {% endif %}
        {% if libraries is not none %}
        set({{ prefix }}_LIBRARIES {{ libraries }} )
        {% endif %}
        {% if definitions is not none %}
        set({{ prefix }}_DEFINITIONS "{{ definitions}}" )
        {% endif %}
        {% endfor %}

        # build_modules_paths comes from last configuration only
        # Some build modules in ConanCenter use try_compile variables and legacy, so this
        # include() needs to happen after the above variables are defined
        {% for build_module in build_modules_paths %}
        message(STATUS "Conan: Including build module from '{{build_module}}'")
        include("{{ build_module }}")
        {% endfor %}

        # Definition of extra CMake variables from cmake_extra_variables

        {% for key, value in extra_variables.items() %}
        set({{ key }} {{ value }})
        {% endfor %}
        """)
