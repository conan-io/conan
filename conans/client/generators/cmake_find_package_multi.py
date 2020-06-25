from jinja2 import Template
import textwrap

from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import (find_transitive_dependencies,
                                                                target_template,
                                                                CMakeFindPackageCommonMacros)
from conans.client.generators.cmake_multi import extend
from conans.model import Generator


class CMakeFindPackageMultiGenerator(Generator):
    config_template = textwrap.dedent("""
        {macros_and_functions}

        # Requires CMake > 3.0
        if(${{CMAKE_VERSION}} VERSION_LESS "3.0")
           message(FATAL_ERROR "The 'cmake_find_package_multi' generator only works with CMake > 3.0" )
        endif()

        include(${{CMAKE_CURRENT_LIST_DIR}}/{name}Targets.cmake)

        {target_props_block}
        {find_dependencies_block}
        """)

    targets_template = textwrap.dedent("""
        if(NOT TARGET {name}::{name})
            add_library({name}::{name} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB CONFIG_FILES "${{_DIR}}/{name}Target-*.cmake")

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

        {%- for comp_name, comp in components %}

        ########### COMPONENT {{ comp_name }} VARIABLES #############################################

        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS_{{ build_type }} {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIR_{{ build_type }} {{ comp.include_path }})
        set({{ pkg_name }}_{{ comp_name }}_INCLUDES_{{ build_type }} {{ comp.include_paths }})
        set({{ pkg_name }}_{{ comp_name }}_LIB_DIRS_{{ build_type }} {{ comp.lib_paths }})
        set({{ pkg_name }}_{{ comp_name }}_RES_DIRS_{{ build_type }} {{ comp.res_paths }})
        set({{ pkg_name }}_{{ comp_name }}_DEFINITIONS_{{ build_type }} {{ comp.defines }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_DEFINITIONS_{{ build_type }} {{ comp.compile_definitions }})
        set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_LIST_{{ build_type }} "{{ comp.cxxflags_list }}" "{{ comp.cflags_list }}")
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

        set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND "")
        conan_find_apple_frameworks({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS_FOUND_{{ build_type }} "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS}' }}" "{{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORK_DIRS}' }}")

        set({{ pkg_name }}_{{ comp_name }}_LIB_TARGETS_{{ build_type }} "")
        set({{ pkg_name }}_{{ comp_name }}_NOT_USED_{{ build_type }} "")
        set({{ pkg_name }}_{{ comp_name }}_LIBS_FRAMEWORKS_DEPS_{{ build_type }} {{ '${'+pkg_name+'_'+comp_name+'_FRAMEWORKS_FOUND}' }} {{ '${'+pkg_name+'_'+comp_name+'_SYSTEM_LIBS}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES_'+build_type+'}' }})
        conan_package_library_targets("{{ '${'+pkg_name+'_'+comp_name+'_LIBS_'+build_type+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIB_DIRS_'+build_type+'}' }}"
                                      "{{ '${'+pkg_name+'_'+comp_name+'_LIBS_FRAMEWORKS_DEPS_'+build_type+'}' }}"
                                      {{ pkg_name }}_{{ comp_name }}_NOT_USED_{{ build_type }}
                                      {{ pkg_name }}_{{ comp_name }}_LIB_TARGETS_{{ build_type }}
                                      ""
                                      "{{ pkg_name }}_{{ comp_name }}")

        set({{ pkg_name }}_{{ comp_name }}_LINK_LIBS_{{ build_type }} {{ '${'+pkg_name+'_'+comp_name+'_LIB_TARGETS_'+build_type+'}' }} {{ '${'+pkg_name+'_'+comp_name+'_DEPENDENCIES_'+build_type+'}' }})

        {%- endfor %}
        """))

    components_targets_tpl = Template(textwrap.dedent("""\
        {%- for comp_name, comp in components %}

        if(NOT TARGET {{ pkg_name }}::{{ pkg_name }}
            add_library({{ pkg_name }}::{{ pkg_name }} INTERFACE IMPORTED)
        endif()

        {%- endfor %}

        if(NOT TARGET {{ pkg_name }}::{{ comp_name }}
            add_library({{ pkg_name }}::{{ comp_name }} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB CONFIG_FILES "${{_DIR}}/{pkg_name}Target-*.cmake")

        foreach(f ${{CONFIG_FILES}})
          include(${{f}})
        endforeach()
        """))

    components_config_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        {{ conan_message }}
        
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

        set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_LINK_LIBRARIES
                         $<$<CONFIG:Release>:{{ '${'+pkg_name+'_'+comp_name+'_LIBRARIES_TARGETS_RELEASE}' }} {{ '${'+pkg_name+'_'+comp_name+'_LINKER_FLAGS_RELEASE_LIST}' }}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_LIBRARIES_TARGETS_RELWITHDEBINFO}} ${{{pkg_name}_LINKER_FLAGS_RELWITHDEBINFO_LIST}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_LIBRARIES_TARGETS_MINSIZEREL}} ${{{name}_LINKER_FLAGS_MINSIZEREL_LIST}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_LIBRARIES_TARGETS_DEBUG}} ${{{pkg_name}_LINKER_FLAGS_DEBUG_LIST}}>)
        set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES
                         $<$<CONFIG:Release>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{name}_INCLUDE_DIRS_RELWITHDEBINFO}}>
                         $<$<CONFIG:MinSizeRel>:${{{name}_INCLUDE_DIRS_MINSIZEREL}}>
                         $<$<CONFIG:Debug>:${{{name}_INCLUDE_DIRS_DEBUG}}>)
        set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_COMPILE_DEFINITIONS
                         $<$<CONFIG:Release>:${{{pkg_name}_COMPILE_DEFINITIONS_RELEASE}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_COMPILE_DEFINITIONS_RELWITHDEBINFO}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_COMPILE_DEFINITIONS_MINSIZEREL}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_COMPILE_DEFINITIONS_DEBUG}}>)
        set_target_properties({{ pkg_name }}::{{ comp_name }} PROPERTIES INTERFACE_COMPILE_OPTIONS
                         $<$<CONFIG:Release>:${{{pkg_name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_COMPILE_OPTIONS_RELWITHDEBINFO_LIST}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_COMPILE_OPTIONS_MINSIZEREL_LIST}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_COMPILE_OPTIONS_DEBUG_LIST}}>)

        {%- endfor %}

        # Assign global target properties
        set_target_properties({{ pkg_name }}::{{ pkg_name }} PROPERTIES INTERFACE_LINK_LIBRARIES
                         $<$<CONFIG:Release>:${{{pkg_name}_LIBRARIES_TARGETS_RELEASE}} ${{{pkg_name}_LINKER_FLAGS_RELEASE_LIST}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_LIBRARIES_TARGETS_RELWITHDEBINFO}} ${{{pkg_name}_LINKER_FLAGS_RELWITHDEBINFO_LIST}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_LIBRARIES_TARGETS_MINSIZEREL}} ${{{pkg_name}_LINKER_FLAGS_MINSIZEREL_LIST}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_LIBRARIES_TARGETS_DEBUG}} ${{{pkg_name}_LINKER_FLAGS_DEBUG_LIST}}>)
        set_target_properties(TARGET {{ pkg_name }}::{{ pkg_name }} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES
                         $<$<CONFIG:Release>:${{{pkg_name}_INCLUDE_DIRS_RELEASE}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_INCLUDE_DIRS_RELWITHDEBINFO}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_INCLUDE_DIRS_MINSIZEREL}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_INCLUDE_DIRS_DEBUG}}>)
        set_target_properties(TARGET {{ pkg_name }}::{{ pkg_name }} PROPERTIES INTERFACE_COMPILE_DEFINITIONS
                         $<$<CONFIG:Release>:${{{pkg_name}_COMPILE_DEFINITIONS_RELEASE}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_COMPILE_DEFINITIONS_RELWITHDEBINFO}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_COMPILE_DEFINITIONS_MINSIZEREL}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_COMPILE_DEFINITIONS_DEBUG}}>)
        set_target_properties(TARGET {{ pkg_name }}::{{ pkg_name }} PROPERTIES INTERFACE_COMPILE_OPTIONS
                         $<$<CONFIG:Release>:${{{pkg_name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                         $<$<CONFIG:RelWithDebInfo>:${{{pkg_name}_COMPILE_OPTIONS_RELWITHDEBINFO_LIST}}>
                         $<$<CONFIG:MinSizeRel>:${{{pkg_name}_COMPILE_OPTIONS_MINSIZEREL_LIST}}>
                         $<$<CONFIG:Debug>:${{{pkg_name}_COMPILE_OPTIONS_DEBUG_LIST}}>)
        """))

    def _get_components(self, pkg_name, pkg_findname, cpp_info):
        find_package_components = []
        for comp_name, comp in self.sorted_components(cpp_info).items():
            comp_findname = self._get_name(cpp_info.components[comp_name])
            deps_cpp_cmake = DepsCppCmake(comp)
            deps_cpp_cmake.public_deps = self._get_component_requires(pkg_name, pkg_findname, comp)
            find_package_components.append((comp_findname, deps_cpp_cmake))
        find_package_components.reverse()  # From the less dependent to most one
        return find_package_components

    def _get_component_requires(self, pkg_name, pkg_findname, comp):
        comp_requires_findnames = []
        for require in comp.requires:
            if COMPONENT_SCOPE in require:
                comp_require_pkg_name, comp_require_comp_name = require.split(COMPONENT_SCOPE)
                comp_require_pkg = self.deps_build_info[comp_require_pkg_name]
                comp_require_pkg_findname = self._get_name(comp_require_pkg)
                if comp_require_comp_name == comp_require_pkg_name:
                    comp_require_comp_findname = comp_require_pkg_findname
                elif comp_require_comp_name in self.deps_build_info[comp_require_pkg_name].components:
                    comp_require_comp = comp_require_pkg.components[comp_require_comp_name]
                    comp_require_comp_findname = self._get_name(comp_require_comp)
                else:
                    raise ConanException("Component '%s' not found in '%s' package requirement"
                                         % (require, comp_require_pkg_name))
            else:
                comp_require_pkg_findname = pkg_findname
                comp_require_comp = self.deps_build_info[pkg_name].components[require]
                comp_require_comp_findname = self._get_name(comp_require_comp)
            f = "{}::{}".format(comp_require_pkg_findname, comp_require_comp_findname)
            comp_requires_findnames.append(f)
        return " ".join(comp_requires_findnames)

    @classmethod
    def _get_name(cls, obj):
        get_name = getattr(obj, "get_name")
        return get_name(cls.name)

    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        build_type = str(self.conanfile.settings.build_type).upper()
        build_type_suffix = "_{}".format(build_type) if build_type else ""
        for pkg_name, cpp_info in self.deps_build_info.dependencies:
            pkg_findname = self._get_name(cpp_info)
            pkg_version = cpp_info.version
            pkg_public_deps = [self._get_name(self.deps_build_info[public_dep]) for public_dep in
                               cpp_info.public_deps]
            ret["{}ConfigVersion.cmake".format(pkg_findname)] = self.config_version_template. \
                format(version=pkg_version)
            if not cpp_info.components:
                public_deps_names = [self.deps_build_info[dep].get_name("cmake_find_package_multi")
                                     for dep in cpp_info.public_deps]
                ret["{}Config.cmake".format(pkg_findname)] = self._config(pkg_findname, cpp_info.version,
                                                                     public_deps_names)
                ret["{}Targets.cmake".format(pkg_findname)] = self.targets_template.format(name=pkg_findname)

                # If any config matches the build_type one, add it to the cpp_info
                dep_cpp_info = extend(cpp_info, build_type.lower())
                deps = DepsCppCmake(dep_cpp_info)
                deps_names = ";".join(["{n}::{n}".format(n=n) for n in public_deps_names])
                find_lib = target_template.format(name=pkg_findname, deps=deps,
                                                  build_type_suffix=build_type_suffix,
                                                  deps_names=deps_names)
                ret["{}Target-{}.cmake".format(pkg_findname, build_type.lower())] = find_lib
            else:
                cpp_info = extend(cpp_info, build_type.lower())
                pkg_info = DepsCppCmake(cpp_info)
                pkg_public_deps_names = ";".join(["{n}::{n}".format(n=n) for n in pkg_public_deps])
                components = self._get_components(pkg_name, pkg_findname, cpp_info)
                global_target_variables = target_template.format(name=pkg_findname, deps=pkg_info,
                                                                 build_type_suffix=build_type_suffix,
                                                                 deps_names=pkg_public_deps_names)
                variables = self.components_target_build_type_tpl.render(
                    pkg_name=pkg_findname,
                    global_target_variables=global_target_variables,
                    build_type=build_type,
                    components=components,
                    conan_find_apple_frameworks=CMakeFindPackageCommonMacros.apple_frameworks_macro,
                    conan_package_library_targets=CMakeFindPackageCommonMacros.conan_package_library_targets
                )
                ret["{}Target-{}.cmake".format(pkg_findname, build_type.lower())] = variables
                targets = self.components_targets_tpl.format(
                    name=pkg_findname,
                    components=components
                )
                ret["{}Targets.cmake".format(pkg_findname)] = targets
                target_config = self.components_config_tpl.render(
                    pkg_name=pkg_findname,
                    components=components,
                    pkg_public_deps=pkg_public_deps,
                    conan_message=CMakeFindPackageCommonMacros.conan_message
                )
                ret["{}Config.cmake".format(pkg_findname)] = target_config

        return ret

    def _config(self, name, version, public_deps_names):
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
                                          target_props_block=targets_props,
                                          find_dependencies_block=find_dependencies_block,
                                          macros_and_functions=macros_and_functions)
        return tmp
