from jinja2 import Template
import textwrap

from conans.client.generators import CMakeFindPackageGenerator
from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import (find_transitive_dependencies,
                                                                target_template,
                                                                CMakeFindPackageCommonMacros)
from conans.client.generators.cmake_multi import extend
from conans.errors import ConanException
from conans.model import Generator
from conans.model.build_info import COMPONENT_SCOPE


class CMakeFindPackageMultiGenerator(CMakeFindPackageGenerator):
    name = "cmake_find_package_multi"
    config_template = textwrap.dedent("""
        {macros_and_functions}

        # Requires CMake > 3.0
        if(${{CMAKE_VERSION}} VERSION_LESS "3.0")
            message(FATAL_ERROR "The 'cmake_find_package_multi' generator only works with CMake > 3.0")
        endif()

        include(${{CMAKE_CURRENT_LIST_DIR}}/{filename}Targets.cmake)

        {target_props_block}
        {find_dependencies_block}
        """)

    targets_template = textwrap.dedent("""
        if(NOT TARGET {name}::{name})
            add_library({name}::{name} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB CONFIG_FILES "${{_DIR}}/{filename}Target-*.cmake")

        foreach(f ${{CONFIG_FILES}})
            include(${{f}})
        endforeach()
        """)

    target_properties = """
# Assign target properties
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_LINK_LIBRARIES
                 $<$<CONFIG:Release>:${{{name}_LIBRARIES_TARGETS_RELEASE}} ${{{name}_LINKER_FLAGS_RELEASE_LIST}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_LIBRARIES_TARGETS_RELWITHDEBINFO}} ${{{name}_LINKER_FLAGS_RELWITHDEBINFO_LIST}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_LIBRARIES_TARGETS_MINSIZEREL}} ${{{name}_LINKER_FLAGS_MINSIZEREL_LIST}}>
                 $<$<CONFIG:Debug>:${{{name}_LIBRARIES_TARGETS_DEBUG}} ${{{name}_LINKER_FLAGS_DEBUG_LIST}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                 $<$<CONFIG:Release>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_INCLUDE_DIRS_RELWITHDEBINFO}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_INCLUDE_DIRS_MINSIZEREL}}>
                 $<$<CONFIG:Debug>:${{{name}_INCLUDE_DIRS_DEBUG}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_COMPILE_DEFINITIONS
                 $<$<CONFIG:Release>:${{{name}_COMPILE_DEFINITIONS_RELEASE}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_DEFINITIONS_RELWITHDEBINFO}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_DEFINITIONS_MINSIZEREL}}>
                 $<$<CONFIG:Debug>:${{{name}_COMPILE_DEFINITIONS_DEBUG}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_COMPILE_OPTIONS
                 $<$<CONFIG:Release>:${{{name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_OPTIONS_RELWITHDEBINFO_LIST}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_OPTIONS_MINSIZEREL_LIST}}>
                 $<$<CONFIG:Debug>:${{{name}_COMPILE_OPTIONS_DEBUG_LIST}}>)
    """

    # https://gitlab.kitware.com/cmake/cmake/blob/master/Modules/BasicConfigVersion-SameMajorVersion.cmake.in
    config_version_template = textwrap.dedent("""
        set(PACKAGE_VERSION "{version}")

        if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
            set(PACKAGE_VERSION_COMPATIBLE FALSE)
        else()
            if("{version}" MATCHES "^([0-9]+)\\\\.")
                set(CVF_VERSION_MAJOR "${{CMAKE_MATCH_1}}")
            else()
                set(CVF_VERSION_MAJOR "{version}")
            endif()

            if(PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR)
                set(PACKAGE_VERSION_COMPATIBLE TRUE)
            else()
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            endif()

            if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                set(PACKAGE_VERSION_EXACT TRUE)
            endif()
        endif()
        """)

    components_target_build_type_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        {{ conan_message }}
        {{ conan_find_apple_frameworks }}
        {{ conan_package_library_targets }}

        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_target_variables }}
        set({{ pkg_name }}_COMPONENTS_{{ build_type }} {{ pkg_components }})

        {%- for comp_name, comp in components %}

        ########### COMPONENT {{ comp_name }} VARIABLES #############################################

        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS_{{ build_type }} {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIR_{{ build_type }} {{ comp.include_path }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDES_{{ build_type }} {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_LIB_DIRS_{{ build_type }} {{ comp.lib_paths }})
        set({{ pkg_name }}_{{ comp_name }}_RES_DIRS_{{ build_type }} {{ comp.res_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEFINITIONS_{{ build_type }} {{ comp.defines }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_DEFINITIONS_{{ build_type }} {{ comp.compile_definitions }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_C_{{ build_type }} "{{ comp.cflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_CXX_{{ build_type }} "{{ comp.cxxflags_list }}")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_{{ build_type }} {{ comp.libs }})
        set({{ pkg_name }}_{{ comp_name }}_SYSTEM_LIBS_{{ build_type }} {{ comp.system_libs }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORK_DIRS_{{ build_type }} {{ comp.framework_paths }})
        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_{{ build_type }} {{ comp.frameworks }})
        set({{ pkg_name }}_{{ comp_name }}_BUILD_MODULES_PATHS_{{ build_type }} {{ comp.build_modules_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEPENDENCIES_{{ build_type }} {{ comp.public_deps }})
        set({{ pkg_name }}_{{ comp_name }}_LINKER_FLAGS_LIST_{{ build_type }}
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{ comp.exelinkflags_list }}>
        )

        ########## COMPONENT {{ comp_name }} FIND LIBRARIES & FRAMEWORKS / DYNAMIC VARS #############

        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND_{{ build_type }} "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND_{{ build_type }} "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_'+build_type+'}' }}" "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORK_DIRS_'+build_type+'}' }}")

        set({{ pkg_name }}_{{ comp_name }}_LIB_TARGETS_{{ build_type }} "")
        set({{ pkg_name }}_{{ comp_name }}_NOT_USED_{{ build_type }} "")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_FRAMEWORKS_DEPS_{{ build_type }} {{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_FOUND_'+build_type+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_SYSTEM_LIBS_'+build_type+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES_'+build_type+'}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_name+'_LIBS_'+build_type+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS_'+build_type+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS_'+build_type+'}' }}"
                                      {{ pkg_name }}_{{ comp_name }}_NOT_USED_{{ build_type }}
                                      {{ pkg_name }}_{{ comp_name }}_LIB_TARGETS_{{ build_type }}
                                      "{{ build_type }}"
                                      "{{ pkg_name }}_{{ comp_name }}")

        set({{ pkg_name }}_{{ comp_name }}_LINK_LIBS_{{ build_type }} {{ '${'+pkg_name+'_'+comp_name+'_LIB_TARGETS_'+build_type+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS_'+build_type+'}' }})

        {%- endfor %}
        """))

    components_targets_tpl = Template(textwrap.dedent("""\
        {%- for comp_name, comp in components %}

        if(NOT TARGET {{ pkg_name }}::{{ comp_name }})
            add_library({{ pkg_name }}::{{ comp_name }} INTERFACE IMPORTED)
        endif()

        {%- endfor %}

        if(NOT TARGET {{ pkg_name }}::{{ pkg_name }})
            add_library({{ pkg_name }}::{{ pkg_name }} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB CONFIG_FILES "${_DIR}/{{ pkg_filename }}Target-*.cmake")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()

        if({{ pkg_name }}_FIND_COMPONENTS)
            foreach(_FIND_COMPONENT {{ '${'+pkg_name+'_FIND_COMPONENTS}' }})
                list(FIND {{ pkg_name }}_COMPONENTS_{{ build_type }} "{{ pkg_name }}::${_FIND_COMPONENT}" _index)
                if(${_index} EQUAL -1)
                    conan_message(FATAL_ERROR "Conan: Component '${_FIND_COMPONENT}' NOT found in package '{{ pkg_name }}'")
                else()
                    conan_message(STATUS "Conan: Component '${_FIND_COMPONENT}' found in package '{{ pkg_name }}'")
                endif()
            endforeach()
        endif()
        """))

    components_config_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        {{ conan_message }}

        # Requires CMake > 3.0
        if(${CMAKE_VERSION} VERSION_LESS "3.0")
            message(FATAL_ERROR "The 'cmake_find_package_multi' generator only works with CMake > 3.0")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ pkg_filename }}Targets.cmake)

        ########## FIND PACKAGE DEPENDENCY ##########################################################
        #############################################################################################

        include(CMakeFindDependencyMacro)

        {%- for public_dep in pkg_public_deps %}

        if(NOT {{ public_dep }}_FOUND)
            if(${CMAKE_VERSION} VERSION_LESS "3.9.0")
                find_package({{ public_dep }} REQUIRED NO_MODULE)
            else()
                find_dependency({{ public_dep }} REQUIRED NO_MODULE)
            endif()
        else()
            message(STATUS "Dependency {{ public_dep }} already found")
        endif()

        {%- endfor %}

        ########## TARGETS PROPERTIES ###############################################################
        #############################################################################################

        {%- for comp_name, comp in components %}
        ########## COMPONENT {{ comp_name }} TARGET PROPERTIES ######################################

        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                         $<$<CONFIG:Release>:{{ '${'+pkg_name+'_'+comp_name+'_LINK_LIBS_RELEASE}' }} {{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_LIST_RELEASE}' }}>
                         $<$<CONFIG:RelWithDebInfo>:{{ '${'+pkg_name+'_'+comp_name+'_LINK_LIBS_RELWITHDEBINFO}' }} {{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_LIST_RELWITHDEBINFO}' }}>
                         $<$<CONFIG:MinSizeRel>:{{ '${'+pkg_name+'_'+comp_name+'_LINK_LIBS_MINSIZEREL}' }} {{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_LIST_MINSIZEREL}' }}>
                         $<$<CONFIG:Debug>:{{ '${'+pkg_name+'_'+comp_name+'_LINK_LIBS_DEBUG}' }} {{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_LIST_DEBUG}' }}>)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                         $<$<CONFIG:Release>:{{ '${'+pkg_name+'_'+comp_name+'_INCLUDE_DIRS_RELEASE}' }}>
                         $<$<CONFIG:RelWithDebInfo>:{{ '${'+pkg_name+'_'+comp_name+'_INCLUDE_DIRS_RELWITHDEBINFO}' }}>
                         $<$<CONFIG:MinSizeRel>:{{ '${'+pkg_name+'_'+comp_name+'_INCLUDE_DIRS_MINSIZEREL}' }}>
                         $<$<CONFIG:Debug>:{{ '${'+pkg_name+'_'+comp_name+'_INCLUDE_DIRS_DEBUG}' }}>)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                         $<$<CONFIG:Release>:{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_DEFINITIONS_RELEASE}' }}>
                         $<$<CONFIG:RelWithDebInfo>:{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_DEFINITIONS_RELWITHDEBINFO}' }}>
                         $<$<CONFIG:MinSizeRel>:{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_DEFINITIONS_MINSIZEREL}' }}>
                         $<$<CONFIG:Debug>:{{ '${'+pkg_name+'_'+comp_name+'_COMPILE_DEFINITIONS_DEBUG}' }}>)
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                         $<$<CONFIG:Release>:
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_C_RELEASE}' }}
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_CXX_RELEASE}' }}>
                         $<$<CONFIG:RelWithDebInfo>:
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_C_RELWITHDEBINFO}' }}
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_CXX_RELWITHDEBINFO}' }}>
                         $<$<CONFIG:MinSizeRel>:
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_C_MINSIZEREL}' }}
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_CXX_MINSIZEREL}' }}>
                         $<$<CONFIG:Debug>:
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_C_DEBUG}' }}
                             {{ '${'+pkg_name+'_'+comp_name+'_COMPILE_OPTIONS_CXX_DEBUG}' }}>)
        set({{ pkg_name }}_{{ comp_name }}_TARGET_PROPERTIES TRUE)

        {%- endfor %}

        ########## GLOBAL TARGET PROPERTIES #########################################################

        if(NOT {{ pkg_name }}_{{ pkg_name }}_TARGET_PROPERTIES)
            set_property(TARGET {{ pkg_name }}::{{ pkg_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                             $<$<CONFIG:Release>:{{ '${'+pkg_name+'_COMPONENTS_RELEASE}' }}>
                             $<$<CONFIG:RelWithDebInfo>:{{ '${'+pkg_name+'_COMPONENTS_RELWITHDEBINFO}' }}>
                             $<$<CONFIG:MinSizeRel>:{{ '${'+pkg_name+'_COMPONENTS_MINSIZEREL}' }}>
                             $<$<CONFIG:Debug>:{{ '${'+pkg_name+'_COMPONENTS_DEBUG}' }}>)
        endif()
        """))

    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        build_type = str(self.conanfile.settings.build_type).upper()
        build_type_suffix = "_{}".format(build_type) if build_type else ""
        for pkg_name, cpp_info in self.deps_build_info.dependencies:
            pkg_filename = self._get_filename(cpp_info)
            pkg_findname = self._get_name(cpp_info)
            pkg_version = cpp_info.version
            pkg_public_deps_names = [self._get_name(self.deps_build_info[public_dep])
                                     for public_dep in cpp_info.public_deps]
            pkg_public_deps_filenames = [self._get_filename(self.deps_build_info[public_dep])
                                         for public_dep in cpp_info.public_deps]
            ret["{}ConfigVersion.cmake".format(pkg_filename)] = self.config_version_template. \
                format(version=pkg_version)
            if not cpp_info.components:
                public_deps_names = [
                    {
                      "name": self.deps_build_info[dep].get_name("cmake_find_package_multi"),
                      "filename": self.deps_build_info[dep].get_filename("cmake_find_package_multi")
                    }
                    for dep in cpp_info.public_deps
                ]
                ret["{}Config.cmake".format(pkg_filename)] = self._config(
                    filename=pkg_filename,
                    name=pkg_findname,
                    version=cpp_info.version,
                    public_deps_names=pkg_public_deps_filenames
                )
                ret["{}Targets.cmake".format(pkg_filename)] = self.targets_template.format(filename=pkg_filename, name=pkg_findname)

                # If any config matches the build_type one, add it to the cpp_info
                dep_cpp_info = extend(cpp_info, build_type.lower())
                deps = DepsCppCmake(dep_cpp_info)
                deps_names = ";".join(["{n}::{n}".format(n=n['name']) for n in public_deps_names])
                find_lib = target_template.format(name=pkg_findname, deps=deps,
                                                  build_type_suffix=build_type_suffix,
                                                  deps_names=deps_names)
                ret["{}Target-{}.cmake".format(pkg_filename, build_type.lower())] = find_lib
            else:
                cpp_info = extend(cpp_info, build_type.lower())
                pkg_info = DepsCppCmake(cpp_info)
                deps_names = ";".join(["{n}::{n}".format(n=n) for n in pkg_public_deps_names])
                components = self._get_components(pkg_name, pkg_findname, cpp_info)
                # Note these are in reversed order, from more dependent to less dependent
                pkg_components = " ".join(["{p}::{c}".format(p=pkg_findname, c=comp_findname) for
                                           comp_findname, _ in reversed(components)])
                global_target_variables = target_template.format(name=pkg_findname, deps=pkg_info,
                                                                 build_type_suffix=build_type_suffix,
                                                                 deps_names=deps_names)
                variables = self.components_target_build_type_tpl.render(
                    pkg_name=pkg_findname,
                    global_target_variables=global_target_variables,
                    pkg_components=pkg_components,
                    build_type=build_type,
                    components=components,
                    conan_find_apple_frameworks=CMakeFindPackageCommonMacros.apple_frameworks_macro,
                    conan_package_library_targets=CMakeFindPackageCommonMacros.conan_package_library_targets
                )
                ret["{}Target-{}.cmake".format(pkg_filename, build_type.lower())] = variables
                targets = self.components_targets_tpl.render(
                    pkg_name=pkg_findname,
                    pkg_filename=pkg_filename,
                    components=components,
                    build_type=build_type
                )
                ret["{}Targets.cmake".format(pkg_filename)] = targets
                target_config = self.components_config_tpl.render(
                    pkg_name=pkg_findname,
                    pkg_filename=pkg_filename,
                    components=components,
                    pkg_public_deps=pkg_public_deps_filenames,
                    conan_message=CMakeFindPackageCommonMacros.conan_message
                )
                ret["{}Config.cmake".format(pkg_filename)] = target_config
        return ret

    def _config(self, filename, name, version, public_deps_names):
        # Builds the XXXConfig.cmake file for one package

        # The common macros
        macros_and_functions = "\n".join([
            CMakeFindPackageCommonMacros.conan_message,
            CMakeFindPackageCommonMacros.apple_frameworks_macro,
            CMakeFindPackageCommonMacros.conan_package_library_targets,
        ])

        # Define the targets properties
        targets_props = self.target_properties.format(name=name)

        # The find_dependencies_block
        find_dependencies_block = ""
        if public_deps_names:
            # Here we are generating only Config files, so do not search for FindXXX modules
            find_dependencies_block = find_transitive_dependencies(public_deps_names,
                                                                   find_modules=False)

        tmp = self.config_template.format(name=name, version=version,
                                          filename=filename,
                                          target_props_block=targets_props,
                                          find_dependencies_block=find_dependencies_block,
                                          macros_and_functions=macros_and_functions)
        return tmp
