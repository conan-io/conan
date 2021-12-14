import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooTarget-release.cmake

"""


class TargetConfigurationTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        name = "" if not self.find_module_mode else "module-"
        name += "{}-Target-{}.cmake".format(self.file_name, self.cmakedeps.configuration.lower())
        return name

    @property
    def context(self):
        deps_targets_names = self.get_deps_targets_names() \
            if not self.conanfile.is_build_context else []

        components_targets_names = self.get_declared_components_targets_names()
        components_names = [(components_target_name.replace("::", "_"), components_target_name)
                            for components_target_name in components_targets_names]

        return {"pkg_name": self.pkg_name,
                "root_target_name": self.root_target_name,
                "config_suffix": self.config_suffix,
                "deps_targets_names": ";".join(deps_targets_names),
                "components_names": components_names,
                "configuration": self.cmakedeps.configuration}

    @property
    def template(self):
        return textwrap.dedent("""\

        {%- macro tvalue(pkg_name, comp_name, var, config_suffix) -%}
            {{'${'+pkg_name+'_'+comp_name+'_'+var+config_suffix+'}'}}
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
        set(_{{ pkg_name }}_DEPENDENCIES{{ config_suffix }} "{{ '${' }}{{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }}} {{ '${' }}{{ pkg_name }}_SYSTEM_LIBS{{ config_suffix }}} {{ deps_targets_names }}")

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
        set({{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }} {{ '"${' }}{{ pkg_name }}_LIBRARIES_TARGETS{{ config_suffix }}{{ '};' }}{{ deps_targets_names }}")
        set({{ pkg_name }}_LIBRARIES{{ config_suffix }} {{ '"${' }}{{ pkg_name }}_LIBRARIES{{ config_suffix }}{{ '};' }}{{ deps_targets_names }}")

        # FIXME: What is the result of this for multi-config? All configs adding themselves to path?
        set(CMAKE_MODULE_PATH {{ '${' }}{{ pkg_name }}_BUILD_DIRS{{ config_suffix }}} {{ '${' }}CMAKE_MODULE_PATH})
        set(CMAKE_PREFIX_PATH {{ '${' }}{{ pkg_name }}_BUILD_DIRS{{ config_suffix }}} {{ '${' }}CMAKE_PREFIX_PATH})

        {%- for comp_variable_name, comp_target_name in components_names %}

        ########## COMPONENT {{ comp_target_name }} FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #############

        set({{ pkg_name }}_{{ comp_variable_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_variable_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORKS'+config_suffix+'}' }}" "{{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORK_DIRS'+config_suffix+'}' }}")

        set({{ pkg_name }}_{{ comp_variable_name }}_LIB_TARGETS{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_variable_name }}_NOT_USED{{ config_suffix }} "")
        set({{ pkg_name }}_{{ comp_variable_name }}_LIBS_FRAMEWORKS_DEPS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORKS_FOUND'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_variable_name+'_SYSTEM_LIBS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_variable_name+'_DEPENDENCIES'+config_suffix+'}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_variable_name+'_LIBS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_LIB_DIRS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }}"
                                      {{ pkg_name }}_{{ comp_variable_name }}_NOT_USED{{ config_suffix }}
                                      {{ pkg_name }}_{{ comp_variable_name }}_LIB_TARGETS{{ config_suffix }}
                                      "{{ config_suffix }}"
                                      "{{ pkg_name }}_{{ comp_variable_name }}")

        set({{ pkg_name }}_{{ comp_variable_name }}_LINK_LIBS{{ config_suffix }} {{ '${'+pkg_name+'_'+comp_variable_name+'_LIB_TARGETS'+config_suffix+'}' }} {{ '${'+pkg_name+'_'+comp_variable_name+'_LIBS_FRAMEWORKS_DEPS'+config_suffix+'}' }})
        {%- endfor %}



        ########## GLOBAL TARGET PROPERTIES {{ configuration }} ########################################
        set_property(TARGET {{root_target_name}}
                     PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_LIBRARIES_TARGETS{{config_suffix}}}
                                                   ${{'{'}}{{pkg_name}}_OBJECTS{{config_suffix}}}> APPEND)
        set_property(TARGET {{root_target_name}}
                     PROPERTY INTERFACE_LINK_OPTIONS
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_LINKER_FLAGS{{config_suffix}}}> APPEND)
        set_property(TARGET {{root_target_name}}
                     PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_INCLUDE_DIRS{{config_suffix}}}> APPEND)
        set_property(TARGET {{root_target_name}}
                     PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_COMPILE_DEFINITIONS{{config_suffix}}}> APPEND)
        set_property(TARGET {{root_target_name}}
                     PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_COMPILE_OPTIONS{{config_suffix}}}> APPEND)

        ########## COMPONENTS TARGET PROPERTIES {{ configuration }} ########################################

        {%- for comp_variable_name, comp_target_name in components_names %}

        ########## COMPONENT {{ comp_target_name }} TARGET PROPERTIES ######################################
        set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'LINK_LIBS', config_suffix)}}
                     {{tvalue(pkg_name, comp_variable_name, 'OBJECTS', config_suffix)}}> APPEND)
        set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_LINK_OPTIONS
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'LINKER_FLAGS', config_suffix)}}> APPEND)
        set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'INCLUDE_DIRS', config_suffix)}}> APPEND)
        set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'COMPILE_DEFINITIONS', config_suffix)}}> APPEND)
        set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<CONFIG:{{ configuration }}>:
                     {{tvalue(pkg_name, comp_variable_name, 'COMPILE_OPTIONS_C', config_suffix)}}
                     {{tvalue(pkg_name, comp_variable_name, 'COMPILE_OPTIONS_CXX', config_suffix)}}> APPEND)
        set({{ pkg_name }}_{{ comp_variable_name }}_TARGET_PROPERTIES TRUE)

        {%- endfor %}

        """)

    def get_declared_components_targets_names(self):
        """Returns a list of component_name"""
        ret = []
        sorted_comps = self.conanfile.cpp_info.get_sorted_components()
        for comp_name, comp in sorted_comps.items():
            ret.append(self.get_component_alias(self.conanfile, comp_name))
        ret.reverse()
        return ret

    def get_deps_targets_names(self):
        """
          - [{foo}::{bar}, ] of the required
        """
        ret = []

        # Get a list of dependencies target names
        # Declared cppinfo.requires or .components[].requires
        visible_host = self.conanfile.dependencies.filter({"build": False, "visible": True})
        visible_host_direct = visible_host.filter({"direct": True})
        if self.conanfile.cpp_info.required_components:
            for dep_name, component_name in self.conanfile.cpp_info.required_components:
                if not dep_name:
                    # Internal dep (no another component)
                    req = self.conanfile
                else:
                    req = visible_host[dep_name]

                component_name = self.get_component_alias(req, component_name)
                ret.append(component_name)
        elif visible_host_direct:
            # Regular external "conanfile.requires" declared, not cpp_info requires
            ret = [self.get_root_target_name(r) for r in visible_host_direct.values()]
        return ret
