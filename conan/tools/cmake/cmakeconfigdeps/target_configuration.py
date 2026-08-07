import textwrap

import jinja2
from jinja2 import Template


class TargetConfigurationTemplate2:
    """
    Foo-Targets-release.cmake / Foo-TargetsBuild-release.cmake

    Thin Jinja renderer. All target/requires logic lives in CMakeConfigDeps.
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
        # TODO: CMake 3.24: Apple Frameworks: https://cmake.org/cmake/help/latest/manual/cmake-generator-expressions.7.html#genex:LINK_LIBRARY
        # TODO: Check why not set_property instead of target_link_libraries
        return textwrap.dedent("""\
        {%- macro config_wrapper(config, value) -%}
             {% if config -%}
             $<$<CONFIG:{{config}}>:{{value}}>
             {%- else -%}
             {{value}}
             {%- endif %}
        {%- endmacro -%}
        set({{pkg_folder_var}} "{{pkg_folder}}")

        # Dependencies finding
        include(CMakeFindDependencyMacro)

        {% for dep, dep_find_mode in dependencies.items() %}
        if(NOT {{dep}}_FOUND)
            find_dependency({{dep}} REQUIRED {{dep_find_mode}})
        endif()
        {% endfor %}

        ################# Libs information ##############
        {% for lib, lib_info in libs.items() %}
        #################### {{lib}} ####################
        if(NOT TARGET {{ lib }})
            message(STATUS "Conan: Target declared imported {{lib_info["type"]}} library '{{lib}}'")
            add_library({{lib}} {{lib_info["type"]}} IMPORTED)
        endif()
        {% for alias in lib_info.get("cmake_target_aliases", []) %}
        if(NOT TARGET {{alias}})
            message(STATUS "Conan: Target declared alias '{{alias}}' for '{{lib}}'")
            add_library({{alias}} ALIAS {{lib}})
        endif()
        {% endfor %}
        {% if lib_info.get("includedirs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     {{config_wrapper(config, lib_info["includedirs"])}})
        {% endif %}
        {% if lib_info.get("defines") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     "{{config_wrapper(config, lib_info["defines"])}}")
        {% endif %}
        {% if lib_info.get("cxxflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     "$<$<COMPILE_LANGUAGE:CXX>:{{config_wrapper(config, lib_info["cxxflags"])}}>")
        {% endif %}
        {% if lib_info.get("cflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     "$<$<COMPILE_LANGUAGE:C>:{{config_wrapper(config, lib_info["cflags"])}}>")
        {% endif %}
        {% if lib_info.get("sharedlinkflags") %}
        {% set linkflags = config_wrapper(config, lib_info["sharedlinkflags"]) %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_OPTIONS
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{linkflags}}>"
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{linkflags}}>")
        {% endif %}
        {% if lib_info.get("exelinkflags") %}
        {% set exeflags = config_wrapper(config, lib_info["exelinkflags"]) %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_OPTIONS
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{exeflags}}>")
        {% endif %}

        {% if lib_info.get("link_languages") %}
        get_property(_languages GLOBAL PROPERTY ENABLED_LANGUAGES)
        if("CXX" IN_LIST _languages)
            list(APPEND _languages "C")
        endif()
        if("CUDA" IN_LIST _languages)
            list(APPEND _languages "C" "CXX")
        endif()
        {% for lang in lib_info["link_languages"] %}
        if(NOT "{{lang}}" IN_LIST _languages)
            message(SEND_ERROR
                    "Target {{lib}} has {{lang}} linkage but {{lang}} not enabled in project()")
        endif()
        set_property(TARGET {{lib}} APPEND PROPERTY
                     IMPORTED_LINK_INTERFACE_LANGUAGES_{{config}} {{lang}})
        {% endfor %}
        {% endif %}
        {% if lib_info.get("location") %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{lib}} PROPERTIES IMPORTED_LOCATION_{{config}}
                              "{{lib_info["location"]}}")
        {% if lib_info.get("no_soname") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_NO_SONAME_{{config}} TRUE)
        {% endif %}
        {% elif lib_info.get("type") == "INTERFACE" %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        {% endif %}
        {% if lib_info.get("link_location") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_IMPLIB_{{config}}
                              "{{lib_info["link_location"]}}")
        {% endif %}

        {% if lib_info.get("requires") %}
        # Information of transitive dependencies
        {% for require_target, link_info in lib_info["requires"].items() %}

        # Requirement {{lib}} -> {{require_target}} (Full link: {{link_info["link"]}})
        {% if link_info["link"] %}
        {% if link_info["link_feature"] %}
        # Link feature: {{link_info["link_feature"]}}
        if(CMAKE_VERSION VERSION_LESS "3.24")
            message(FATAL_ERROR "The 'CMakeConfigDeps' generator LINK_FEATURE property only works with CMake >= 3.24")
        endif()
        {% endif %}
        # set property allows to append, and lib_info[requires] will iterate
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
            {% if link_info["link_feature"] %}
                     "$<LINK_LIBRARY:{{link_info["link_feature"]}},{{config_wrapper(config, require_target)}}>")
            {% else %}
                     "{{config_wrapper(config, require_target)}}")
            {% endif %}
        {% else %}
        if(CMAKE_VERSION VERSION_LESS "3.27")
            message(FATAL_ERROR "The 'CMakeConfigDeps' generator COMPILE_ONLY expression only works with CMake >= 3.27")
        endif()
        # If the headers trait is not there, this will do nothing
        target_link_libraries({{lib}} INTERFACE
                              $<COMPILE_ONLY:{{config_wrapper(config, require_target)}}> )
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_LINK_DEPENDENT_LIBRARIES_{{config}}
                     {{require_target}})
        {% endif %}
        {% endfor %}
        {% endif %}

        {% if lib_info.get("system_libs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                     {{config_wrapper(config, lib_info["system_libs"])}})
        {% endif %}
        {% if lib_info.get("frameworks") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                     "{{config_wrapper(config, lib_info["frameworks"])}}")
        {% endif %}
        {% if lib_info.get("package_framework") %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{lib}} PROPERTIES
            IMPORTED_LOCATION_{{config}} "{{lib_info["package_framework"]["location"]}}"
            FRAMEWORK TRUE)
        if(CMAKE_VERSION VERSION_LESS "3.24")
            set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                         $<$<COMPILE_LANGUAGE:CXX>:-F{{lib_info["package_framework"]["frameworkdir"]}}>)
            set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                         $<$<COMPILE_LANGUAGE:C>:-F{{lib_info["package_framework"]["frameworkdir"]}}>)
        endif()
        {% endif %}

        {% if lib_info.get("sources") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_SOURCES
                     {{config_wrapper(config, lib_info["sources"] )}})
        {% endif %}
        {% endfor %}

        ################# Exes information ##############
        {% for exe, location in exes.items() %}
        #################### {{exe}} ####################
        if(NOT TARGET {{ exe }})
            message(STATUS "Conan: Target declared imported executable '{{exe}}' {{context}}")
            add_executable({{exe}} IMPORTED)
        else()
            get_property(_context TARGET {{exe}} PROPERTY CONAN_CONTEXT)
            if(NOT $${_context} STREQUAL "{{context}}")
                message(STATUS "Conan: Exe {{exe}} was already defined in ${_context}")
                get_property(_configurations TARGET {{exe}} PROPERTY IMPORTED_CONFIGURATIONS)
                message(STATUS "Conan: Exe {{exe}} defined configurations: ${_configurations}")
                foreach(_config ${_configurations})
                    set_property(TARGET {{exe}} PROPERTY IMPORTED_LOCATION_${_config})
                endforeach()
                set_property(TARGET {{exe}} PROPERTY IMPORTED_CONFIGURATIONS)
            endif()
        endif()
        set_property(TARGET {{exe}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{exe}} PROPERTIES IMPORTED_LOCATION_{{config}} "{{location}}")
        set_property(TARGET {{exe}} PROPERTY CONAN_CONTEXT "{{context}}")
        {% endfor %}
        """)
