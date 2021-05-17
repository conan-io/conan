import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooTarget-release.cmake

"""


class TargetConfigurationTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        return "{}Target-{}.cmake".format(self.pkg_name, self.configuration.lower())

    @property
    def context(self):

        return {"pkg_name": self.pkg_name,
                "config_suffix": self.config_suffix,
                "dependency_names": " ".join(self.get_dependency_names()),
                "components_names":  self.get_required_components_names(),
                "configuration": self.configuration}

    @property
    def template(self):
        return textwrap.dedent("""\

        {%- macro tvalue(pkg_name, comp_name, var, config_suffix) -%}
            {%- if comp_name == pkg_name -%}
                {{'${'+pkg_name+'_'+var+config_suffix+'}'}}
            {%- else -%}
                {{'${'+pkg_name+'_'+comp_name+'_'+var+config_suffix+'}'}}
            {%- endif -%}
        {%- endmacro -%}

        ########### VARIABLES #######################################################################
        #############################################################################################

        set({{ pkg_name }}_COMPILE_OPTIONS{{ config_suffix }}
        "$<$<COMPILE_LANGUAGE:CXX>{{ ':${' }}{{ pkg_name }}_COMPILE_OPTIONS_CXX{{ config_suffix }}}>"
        "$<$<COMPILE_LANGUAGE:C>{{ ':${' }}{{ pkg_name }}_COMPILE_OPTIONS_C{{ config_suffix }}}>")

        set({{ pkg_name }}_LINKER_FLAGS{{ config_suffix }}
        "$<$<STREQUAL{{ ':$' }}<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>{{ ':${' }}{{ pkg_name }}_SHARED_LINK_FLAGS{{ config_suffix }}}>"
        "$<$<STREQUAL{{ ':$' }}<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>{{ ':${' }}{{ pkg_name }}_SHARED_LINK_FLAGS{{ config_suffix }}}>"
        "$<$<STREQUAL{{ ':$' }}<TARGET_PROPERTY:TYPE>,EXECUTABLE>{{ ':${' }}{{ pkg_name }}_EXE_LINK_FLAGS{{ config_suffix }}}>")

        set({{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "") # Will be filled later
        conan_find_apple_frameworks({{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${' }}{{ pkg_name }}_FRAMEWORKS{{ config_suffix }}}" "{{ '${' }}{{ pkg_name }}_FRAMEWORK_DIRS{{ config_suffix }}}")

        # Gather all the libraries that should be linked to the targets (do not touch existing variables)
        set(_{{ pkg_name }}_DEPENDENCIES{{ config_suffix }} "{{ '${' }}{{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }}} {{ '${' }}{{ pkg_name }}_SYSTEM_LIBS{{ config_suffix }}} {{ dependency_names }}")

        set({{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }} "") # Will be filled later
        set({{ pkg_name }}_LIBRARIES{{ config_suffix }} "") # Will be filled later
        conan_package_library_targets("{{ '${' }}{{ pkg_name }}_LIBS{{ config_suffix }}}"    # libraries
                                      "{{ '${' }}{{ pkg_name }}_LIB_DIRS{{ config_suffix }}}" # package_libdir
                                      "{{ '${' }}_{{ pkg_name }}_DEPENDENCIES{{ config_suffix }}}" # deps
                                      {{ pkg_name }}_LIBRARIES{{ config_suffix }}   # out_libraries
                                      {{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }}  # out_libraries_targets
                                      "{{ config_suffix }}"  # config_suffix
                                      "{{ pkg_name }}")    # package_name

        foreach(_FRAMEWORK {{ '${' }}{{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }}})
            list(APPEND {{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }} ${_FRAMEWORK})
            list(APPEND {{ pkg_name }}_LIBRARIES{{ config_suffix }} ${_FRAMEWORK})
        endforeach()

        foreach(_SYSTEM_LIB {{ '${' }}{{ pkg_name }}_SYSTEM_LIBS{{ config_suffix }}})
            list(APPEND {{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }} ${_SYSTEM_LIB})
            list(APPEND {{ pkg_name }}_LIBRARIES{{ config_suffix }} ${_SYSTEM_LIB})
        endforeach()

        # We need to add our requirements too
        set({{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }} {{ '${' }}{{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }}} {{ dependency_names }})
        set({{ pkg_name }}_LIBRARIES{{ config_suffix }} {{ '${' }}{{ pkg_name }}_LIBRARIES{{ config_suffix }}} {{ dependency_names }})

        # FIXME: What is the result of this for multi-config? All configs adding themselves to path?
        set(CMAKE_MODULE_PATH {{ '${' }}{{ pkg_name }}_BUILD_DIRS{{ config_suffix }}} {{ '${' }}CMAKE_MODULE_PATH})
        set(CMAKE_PREFIX_PATH {{ '${' }}{{ pkg_name }}_BUILD_DIRS{{ config_suffix }}} {{ '${' }}CMAKE_PREFIX_PATH})

        {%- for comp_name in components_names %}

        ########## COMPONENT {{ comp_name }} FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #############

        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS'+config_suffix+'}' }}" "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORK_DIRS'+config_suffix+'}' }}")

        set({{ pkg_name }}_{{ comp_name }}_LIB_TARGETS{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_name }}_NOT_USED{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_FRAMEWORKS_DEPS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_FOUND'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_SYSTEM_LIBS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES'+config_suffix+'}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_name+'_LIBS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }}"
                                      {{ pkg_name }}_{{ comp_name }}_NOT_USED{{ config_suffix }}
                                      {{ pkg_name }}_{{ comp_name }}_LIB_TARGETS{{ config_suffix }}
                                      "{{ config_suffix }}"
                                      "{{ pkg_name }}_{{ comp_name }}")

        set({{ pkg_name }}_{{ comp_name }}_LINK_LIBS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_name+'_LIB_TARGETS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }})
        {%- endfor %}


        ########## GLOBAL TARGET PROPERTIES {{ configuration }} ########################################
        set_property(TARGET {{pkg_name}}::{{pkg_name}}
                     PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_LIBRARIES_TARGETS{{config_suffix}}}
                                                   ${{'{'}}{{pkg_name}}_LINKER_FLAGS{{config_suffix}}}> APPEND)
        set_property(TARGET {{pkg_name}}::{{pkg_name}}
                     PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_INCLUDE_DIRS{{config_suffix}}}> APPEND)
        set_property(TARGET {{pkg_name}}::{{pkg_name}}
                     PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_COMPILE_DEFINITIONS{{config_suffix}}}> APPEND)
        set_property(TARGET {{pkg_name}}::{{pkg_name}}
                     PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_COMPILE_OPTIONS{{config_suffix}}}> APPEND)

        ########## COMPONENTS TARGET PROPERTIES {{ configuration }} ########################################

        {%- for comp_name in components_names %}
        ########## COMPONENT {{ comp_name }} TARGET PROPERTIES ######################################
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_name, 'LINK_LIBS', config_suffix)}}
                     {{tvalue(pkg_name, comp_name, 'LINKER_FLAGS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_name, 'INCLUDE_DIRS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_name, 'COMPILE_DEFINITIONS', config_suffix)}}> APPEND)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<CONFIG:{{ configuration }}>:
                     {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_C', config_suffix)}}
                     {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_CXX', config_suffix)}}> APPEND)
        set({{ pkg_name }}_{{ comp_name }}_TARGET_PROPERTIES TRUE)

        {%- endfor %}

        """)

    def get_required_components_names(self):
        """Returns a list of component_name"""
        ret = []
        sorted_comps = self.conanfile.new_cpp_info.get_sorted_components()
        for comp_name, comp in sorted_comps.items():
            ret.append(comp_name)
        ret.reverse()
        return ret
