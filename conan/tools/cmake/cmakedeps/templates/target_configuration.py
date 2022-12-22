import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate
from conans.model.dependencies import get_transitive_requires

"""

FooTarget-release.cmake

"""


class TargetConfigurationTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        name = "" if not self.generating_module else "module-"
        name += "{}-Target-{}.cmake".format(self.file_name, self.cmakedeps.configuration.lower())
        return name

    @property
    def context(self):
        deps_targets_names = self.get_deps_targets_names() \
            if not self.require.build else []

        components_targets_names = self.get_declared_components_targets_names()
        components_names = [(components_target_name.replace("::", "_"), components_target_name)
                            for components_target_name in components_targets_names]

        is_win = self.conanfile.settings.get_safe("os") == "Windows"
        auto_link = self.conanfile.cpp_info.get_property("cmake_set_interface_link_directories")
        return {"pkg_name": self.pkg_name,
                "root_target_name": self.root_target_name,
                "config_suffix": self.config_suffix,
                "config": self.configuration.upper(),
                "deps_targets_names": ";".join(deps_targets_names),
                "components_names": components_names,
                "configuration": self.cmakedeps.configuration,
                "set_interface_link_directories": auto_link and is_win}

    @property
    def template(self):
        return textwrap.dedent("""\
        # Avoid multiple calls to find_package to append duplicated properties to the targets
        include_guard()

        {%- macro tvalue(pkg_name, comp_name, var, config_suffix) -%}
            {{'${'+pkg_name+'_'+comp_name+'_'+var+config_suffix+'}'}}
        {%- endmacro -%}

        ########### VARIABLES #######################################################################
        #############################################################################################
        set({{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "") # Will be filled later
        conan_find_apple_frameworks({{ pkg_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${' }}{{ pkg_name }}_FRAMEWORKS{{ config_suffix }}}" "{{ '${' }}{{ pkg_name }}_FRAMEWORK_DIRS{{ config_suffix }}}")

        set({{ pkg_name }}_LIBRARIES_TARGETS "") # Will be filled later


        ######## Create an interface target to contain all the dependencies (frameworks, system and conan deps)
        if(NOT TARGET {{ pkg_name+'_DEPS_TARGET'}})
            add_library({{ pkg_name+'_DEPS_TARGET'}} INTERFACE IMPORTED)
        endif()

        set_property(TARGET {{ pkg_name + '_DEPS_TARGET'}}
                     PROPERTY INTERFACE_LINK_LIBRARIES
                     $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_FRAMEWORKS_FOUND'+config_suffix+'}' }}>
                     $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_SYSTEM_LIBS'+config_suffix+'}' }}>
                     $<$<CONFIG:{{configuration}}>:{{ deps_targets_names }}>
                     APPEND)

        ####### Find the libraries declared in cpp_info.libs, create an IMPORTED target for each one and link the
        ####### {{pkg_name}}_DEPS_TARGET to all of them
        conan_package_library_targets("{{ '${' }}{{ pkg_name }}_LIBS{{ config_suffix }}}"    # libraries
                                      "{{ '${' }}{{ pkg_name }}_LIB_DIRS{{ config_suffix }}}" # package_libdir
                                      "{{ '${' }}{{ pkg_name }}_BIN_DIRS{{ config_suffix }}}" # package_bindir
                                      "{{ '${' }}{{ pkg_name }}_LIBRARY_TYPE{{ config_suffix }}}"
                                      "{{ '${' }}{{ pkg_name }}_IS_HOST_WINDOWS{{ config_suffix }}}"
                                      {{ pkg_name + '_DEPS_TARGET'}}
                                      {{ pkg_name }}_LIBRARIES_TARGETS  # out_libraries_targets
                                      "{{ config_suffix }}"
                                      "{{ pkg_name }}"    # package_name
                                      "{{ '${' }}{{ pkg_name }}_NO_SONAME_MODE{{ config_suffix }}}")  # soname

        # FIXME: What is the result of this for multi-config? All configs adding themselves to path?
        set(CMAKE_MODULE_PATH {{ '${' }}{{ pkg_name }}_BUILD_DIRS{{ config_suffix }}} {{ '${' }}CMAKE_MODULE_PATH})

        {% if not components_names %}

        ########## GLOBAL TARGET PROPERTIES {{ configuration }} ########################################
            set_property(TARGET {{root_target_name}}
                         PROPERTY INTERFACE_LINK_LIBRARIES
                         $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_OBJECTS'+config_suffix+'}' }}>
                         $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_LIBRARIES_TARGETS}>
                         APPEND)

            if("{{ '${' }}{{ pkg_name }}_LIBS{{ config_suffix }}}" STREQUAL "")
                # If the package is not declaring any "cpp_info.libs" the package deps, system libs,
                # frameworks etc are not linked to the imported targets and we need to do it to the
                # global target
                set_property(TARGET {{root_target_name}}
                             PROPERTY INTERFACE_LINK_LIBRARIES
                             {{pkg_name}}_DEPS_TARGET
                             APPEND)
            endif()

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

            {%- if set_interface_link_directories %}

            # This is only used for '#pragma comment(lib, "foo")' (automatic link)
            set_property(TARGET {{root_target_name}}
                         PROPERTY INTERFACE_LINK_DIRECTORIES
                         $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_LIB_DIRS{{config_suffix}}}> APPEND)
            {%- endif %}


        {%- else %}

        ########## COMPONENTS TARGET PROPERTIES {{ configuration }} ########################################

            {%- for comp_variable_name, comp_target_name in components_names %}


            ########## COMPONENT {{ comp_target_name }} #############

                set({{ pkg_name }}_{{ comp_variable_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "")
                conan_find_apple_frameworks({{ pkg_name }}_{{ comp_variable_name }}_FRAMEWORKS_FOUND{{ config_suffix }} "{{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORKS'+config_suffix+'}' }}" "{{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORK_DIRS'+config_suffix+'}' }}")

                set({{ pkg_name }}_{{ comp_variable_name }}_LIBRARIES_TARGETS "")

                ######## Create an interface target to contain all the dependencies (frameworks, system and conan deps)
                if(NOT TARGET {{ pkg_name + '_' + comp_variable_name + '_DEPS_TARGET'}})
                    add_library({{ pkg_name + '_' + comp_variable_name + '_DEPS_TARGET'}} INTERFACE IMPORTED)
                endif()

                set_property(TARGET {{ pkg_name + '_' + comp_variable_name + '_DEPS_TARGET'}}
                             PROPERTY INTERFACE_LINK_LIBRARIES
                             $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_'+comp_variable_name+'_FRAMEWORKS_FOUND'+config_suffix+'}' }}>
                             $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_'+comp_variable_name+'_SYSTEM_LIBS'+config_suffix+'}' }}>
                             $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_'+comp_variable_name+'_DEPENDENCIES'+config_suffix+'}' }}>
                             APPEND)

                ####### Find the libraries declared in cpp_info.component["xxx"].libs,
                ####### create an IMPORTED target for each one and link the '{{pkg_name}}_{{comp_variable_name}}_DEPS_TARGET' to all of them
                conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_variable_name+'_LIBS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_LIB_DIRS'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_BIN_DIRS'+config_suffix+'}' }}" # package_bindir
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_LIBRARY_TYPE'+config_suffix+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_IS_HOST_WINDOWS'+config_suffix+'}' }}"
                                      {{ pkg_name + '_' + comp_variable_name + '_DEPS_TARGET'}}
                                      {{ pkg_name }}_{{ comp_variable_name }}_LIBRARIES_TARGETS
                                      "{{ config_suffix }}"
                                      "{{ pkg_name }}_{{ comp_variable_name }}"
                                      "{{ '${'+pkg_name+'_'+comp_variable_name+'_NO_SONAME_MODE'+config_suffix+'}' }}")


                ########## TARGET PROPERTIES #####################################
                set_property(TARGET {{comp_target_name}}
                             PROPERTY INTERFACE_LINK_LIBRARIES
                             $<$<CONFIG:{{configuration}}>:{{ '${'+pkg_name+'_'+comp_variable_name+'_OBJECTS'+config_suffix+'}' }}>
                             $<$<CONFIG:{{configuration}}>:${{'{'}}{{pkg_name}}_{{comp_variable_name}}_LIBRARIES_TARGETS}>
                             APPEND)

                if("{{ '${' }}{{ pkg_name }}_{{comp_variable_name}}_LIBS{{ config_suffix }}}" STREQUAL "")
                    # If the component is not declaring any "cpp_info.components['foo'].libs" the system, frameworks etc are not
                    # linked to the imported targets and we need to do it to the global target
                    set_property(TARGET {{comp_target_name}}
                                 PROPERTY INTERFACE_LINK_LIBRARIES
                                 {{pkg_name}}_{{comp_variable_name}}_DEPS_TARGET
                                 APPEND)
                endif()

                set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_LINK_OPTIONS
                             $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'LINKER_FLAGS', config_suffix)}}> APPEND)
                set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                             $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'INCLUDE_DIRS', config_suffix)}}> APPEND)
                set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                             $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'COMPILE_DEFINITIONS', config_suffix)}}> APPEND)
                set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                             $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'COMPILE_OPTIONS', config_suffix)}}> APPEND)

                {%- if set_interface_link_directories %}
                # This is only used for '#pragma comment(lib, "foo")' (automatic link)
                set_property(TARGET {{ comp_target_name }} PROPERTY INTERFACE_LINK_DIRECTORIES
                             $<$<CONFIG:{{ configuration }}>:{{tvalue(pkg_name, comp_variable_name, 'LIB_DIRS', config_suffix)}}> APPEND)

                {%- endif %}
            {%endfor %}


            ########## AGGREGATED GLOBAL TARGET WITH THE COMPONENTS #####################
            {%- for comp_variable_name, comp_target_name in components_names %}

            set_property(TARGET {{root_target_name}} PROPERTY INTERFACE_LINK_LIBRARIES {{ comp_target_name }} APPEND)

            {%- endfor %}


        {%- endif %}


        ########## For the modules (FindXXX)
        set({{ pkg_name }}_LIBRARIES{{ config_suffix }} {{root_target_name}})

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
        transitive_reqs = get_transitive_requires(self.cmakedeps._conanfile, self.conanfile)
        if self.conanfile.cpp_info.required_components:
            for dep_name, component_name in self.conanfile.cpp_info.required_components:
                try:
                    # if not dep_name, it is internal, from current self.conanfile
                    req = transitive_reqs[dep_name] if dep_name is not None else self.conanfile
                except KeyError:
                    # if it raises it means the required component is not in the direct_host
                    # dependencies, maybe it has been filtered out by traits => Skip
                    pass
                else:
                    component_name = self.get_component_alias(req, component_name)
                    ret.append(component_name)
        elif transitive_reqs:
            # Regular external "conanfile.requires" declared, not cpp_info requires
            ret = [self.get_root_target_name(r) for r in transitive_reqs.values()]
        return ret
