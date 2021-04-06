import os
import textwrap

from jinja2 import Template

from conans.errors import ConanException
from conans.model.build_info import CppInfo, merge_dicts
from conans.util.conan_v2_mode import conan_v2_error
from conans.util.files import save

COMPONENT_SCOPE = "::"

conan_message = textwrap.dedent("""
    function(conan_message MESSAGE_OUTPUT)
        if(NOT CONAN_CMAKE_SILENT_OUTPUT)
            message(${ARGV${0}})
        endif()
    endfunction()
    """)


apple_frameworks_macro = textwrap.dedent("""
   macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
       if(APPLE)
           foreach(_FRAMEWORK ${FRAMEWORKS})
               # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
               find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAME ${_FRAMEWORK} PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
               if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                   list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
               else()
                   message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${FRAMEWORKS_DIRS}")
               endif()
           endforeach()
       endif()
   endmacro()
   """)


conan_package_library_targets = textwrap.dedent("""
   function(conan_package_library_targets libraries package_libdir deps out_libraries out_libraries_target build_type package_name)
       unset(_CONAN_ACTUAL_TARGETS CACHE)

       foreach(_LIBRARY_NAME ${libraries})
           find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                        NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
           if(CONAN_FOUND_LIBRARY)
               conan_message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
               list(APPEND _out_libraries ${CONAN_FOUND_LIBRARY})

               # Create a micro-target for each lib/a found
               set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${build_type})
               if(NOT TARGET ${_LIB_NAME})
                   # Create a micro-target for each lib/a found
                   add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                   set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                   set(_CONAN_ACTUAL_TARGETS ${_CONAN_ACTUAL_TARGETS} ${_LIB_NAME})
               else()
                   conan_message(STATUS "Skipping already existing target: ${_LIB_NAME}")
               endif()
               list(APPEND _out_libraries_target ${_LIB_NAME})
               conan_message(STATUS "Found: ${CONAN_FOUND_LIBRARY}")
           else()
               conan_message(ERROR "Library ${_LIBRARY_NAME} not found in package")
           endif()
           unset(CONAN_FOUND_LIBRARY CACHE)
       endforeach()

       # Add all dependencies to all targets
       string(REPLACE " " ";" deps_list "${deps}")
       foreach(_CONAN_ACTUAL_TARGET ${_CONAN_ACTUAL_TARGETS})
           set_property(TARGET ${_CONAN_ACTUAL_TARGET} PROPERTY INTERFACE_LINK_LIBRARIES "${deps_list}")
       endforeach()

       set(${out_libraries} ${_out_libraries} PARENT_SCOPE)
       set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
   endfunction()
   """)


variables_template = """
set({name}_INCLUDE_DIRS{build_type_suffix} {deps.include_paths})
set({name}_RES_DIRS{build_type_suffix} {deps.res_paths})
set({name}_DEFINITIONS{build_type_suffix} {deps.defines})
set({name}_SHARED_LINK_FLAGS{build_type_suffix} {deps.sharedlinkflags_list})
set({name}_EXE_LINK_FLAGS{build_type_suffix} {deps.exelinkflags_list})
set({name}_COMPILE_DEFINITIONS{build_type_suffix} {deps.compile_definitions})
set({name}_COMPILE_OPTIONS_C{build_type_suffix} {deps.cflags_list})
set({name}_COMPILE_OPTIONS_CXX{build_type_suffix} {deps.cxxflags_list})
set({name}_LIB_DIRS{build_type_suffix} {deps.lib_paths})
set({name}_LIBS{build_type_suffix} {deps.libs})
set({name}_SYSTEM_LIBS{build_type_suffix} {deps.system_libs})
set({name}_FRAMEWORK_DIRS{build_type_suffix} {deps.framework_paths})
set({name}_FRAMEWORKS{build_type_suffix} {deps.frameworks})
set({name}_BUILD_MODULES_PATHS{build_type_suffix} {deps.build_modules_paths})
set({name}_BUILD_DIRS{build_type_suffix} {deps.build_paths})
# Missing the dependencies information here
"""


dynamic_variables_template = """

set({name}_COMPILE_OPTIONS{build_type_suffix}
        "$<$<COMPILE_LANGUAGE:CXX>:${{{name}_COMPILE_OPTIONS_CXX{build_type_suffix}}}>"
        "$<$<COMPILE_LANGUAGE:C>:${{{name}_COMPILE_OPTIONS_C{build_type_suffix}}}>")

set({name}_LINKER_FLAGS{build_type_suffix}
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{{name}_SHARED_LINK_FLAGS{build_type_suffix}}}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{{name}_SHARED_LINK_FLAGS{build_type_suffix}}}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{{name}_EXE_LINK_FLAGS{build_type_suffix}}}>")

set({name}_FRAMEWORKS_FOUND{build_type_suffix} "") # Will be filled later
conan_find_apple_frameworks({name}_FRAMEWORKS_FOUND{build_type_suffix} "${{{name}_FRAMEWORKS{build_type_suffix}}}" "${{{name}_FRAMEWORK_DIRS{build_type_suffix}}}")

# Gather all the libraries that should be linked to the targets (do not touch existing variables):
set(_{name}_DEPENDENCIES{build_type_suffix} "${{{name}_FRAMEWORKS_FOUND{build_type_suffix}}} ${{{name}_SYSTEM_LIBS{build_type_suffix}}} {deps_names}")

set({name}_LIBRARIES_TARGETS{build_type_suffix} "") # Will be filled later, if CMake 3
set({name}_LIBRARIES{build_type_suffix} "") # Will be filled later
conan_package_library_targets("${{{name}_LIBS{build_type_suffix}}}"           # libraries
                              "${{{name}_LIB_DIRS{build_type_suffix}}}"       # package_libdir
                              "${{_{name}_DEPENDENCIES{build_type_suffix}}}"  # deps
                              {name}_LIBRARIES{build_type_suffix}             # out_libraries
                              {name}_LIBRARIES_TARGETS{build_type_suffix}     # out_libraries_targets
                              "{build_type_suffix}"                           # build_type
                              "{name}")                                       # package_name

foreach(_FRAMEWORK ${{{name}_FRAMEWORKS_FOUND{build_type_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_FRAMEWORK}})
    list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_FRAMEWORK}})
endforeach()

foreach(_SYSTEM_LIB ${{{name}_SYSTEM_LIBS{build_type_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_SYSTEM_LIB}})
    list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_SYSTEM_LIB}})
endforeach()

# We need to add our requirements too
set({name}_LIBRARIES_TARGETS{build_type_suffix} "${{{name}_LIBRARIES_TARGETS{build_type_suffix}}};{deps_names}")
set({name}_LIBRARIES{build_type_suffix} "${{{name}_LIBRARIES{build_type_suffix}}};{deps_names}")


# FIXME: What is the result of this for multi-config? All configs adding themselves to path?
set(CMAKE_MODULE_PATH ${{{name}_BUILD_DIRS{build_type_suffix}}} ${{CMAKE_MODULE_PATH}})
set(CMAKE_PREFIX_PATH ${{{name}_BUILD_DIRS{build_type_suffix}}} ${{CMAKE_PREFIX_PATH}})
"""


def find_transitive_dependencies(public_deps_filenames):
    # https://github.com/conan-io/conan/issues/4994
    # https://github.com/conan-io/conan/issues/5040
    find = textwrap.dedent("""
        if(NOT {dep_filename}_FOUND)
            find_dependency({dep_filename} REQUIRED NO_MODULE)
        endif()
        """)
    lines = ["", "# Library dependencies", "include(CMakeFindDependencyMacro)"]
    for dep_filename in public_deps_filenames:
        lines.append(find.format(dep_filename=dep_filename))
    return "\n".join(lines)


# FIXME: Can we remove the config (multi-config package_info with .debug .release)?
def extend(cpp_info, config):
    """ adds the specific config configuration to the common one
    """
    config_info = cpp_info.configs.get(config)
    if config_info:
        def add_lists(seq1, seq2):
            return seq1 + [s for s in seq2 if s not in seq1]

        result = CppInfo(str(config_info), config_info.rootpath)
        result.filter_empty = cpp_info.filter_empty
        result.includedirs = add_lists(cpp_info.includedirs, config_info.includedirs)
        result.libdirs = add_lists(cpp_info.libdirs, config_info.libdirs)
        result.bindirs = add_lists(cpp_info.bindirs, config_info.bindirs)
        result.resdirs = add_lists(cpp_info.resdirs, config_info.resdirs)
        result.builddirs = add_lists(cpp_info.builddirs, config_info.builddirs)
        result.libs = cpp_info.libs + config_info.libs
        result.defines = cpp_info.defines + config_info.defines
        result.cflags = cpp_info.cflags + config_info.cflags
        result.cxxflags = cpp_info.cxxflags + config_info.cxxflags
        result.sharedlinkflags = cpp_info.sharedlinkflags + config_info.sharedlinkflags
        result.exelinkflags = cpp_info.exelinkflags + config_info.exelinkflags
        result.system_libs = add_lists(cpp_info.system_libs, config_info.system_libs)
        result.build_modules = merge_dicts(cpp_info.build_modules, config_info.build_modules)
        return result
    return cpp_info


class DepsCppCmake(object):
    def __init__(self, cpp_info, generator_name):
        def join_paths(paths):
            """
            Paths are doubled quoted, and escaped (but spaces)
            e.g: set(LIBFOO_INCLUDE_DIRS "/path/to/included/dir" "/path/to/included/dir2")
            """
            return "\n\t\t\t".join('"%s"'
                                   % p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
                                   for p in paths)

        def join_flags(separator, values):
            # Flags have to be escaped
            return separator.join(v.replace('\\', '\\\\').replace('$', '\\$').replace('"', '\\"')
                                  for v in values)

        def join_defines(values, prefix=""):
            # Defines have to be escaped, included spaces
            return "\n\t\t\t".join('"%s%s"' % (prefix, v.replace('\\', '\\\\').replace('$', '\\$').
                                   replace('"', '\\"'))
                                   for v in values)

        def join_paths_single_var(values):
            """
            semicolon-separated list of dirs:
            e.g: set(LIBFOO_INCLUDE_DIR "/path/to/included/dir;/path/to/included/dir2")
            """
            return '"%s"' % ";".join(p.replace('\\', '/').replace('$', '\\$') for p in values)

        def format_link_flags(link_flags):
            result = []
            for f in link_flags:
                if f.startswith("-"):
                    result.append(f)
                else:
                    if f.startswith("/"):  # msvc link flag
                        f = f[1:]  # Remove the initial / and use only "-"
                    result.append("-{}".format(f))
            return result

        self.include_paths = join_paths(cpp_info.include_paths)
        self.include_path = join_paths_single_var(cpp_info.include_paths)
        self.lib_paths = join_paths(cpp_info.lib_paths)
        self.res_paths = join_paths(cpp_info.res_paths)
        self.bin_paths = join_paths(cpp_info.bin_paths)
        self.build_paths = join_paths(cpp_info.build_paths)
        self.src_paths = join_paths(cpp_info.src_paths)
        self.framework_paths = join_paths(cpp_info.framework_paths)
        self.libs = join_flags(" ", cpp_info.libs)
        self.system_libs = join_flags(" ", cpp_info.system_libs)
        self.frameworks = join_flags(" ", cpp_info.frameworks)
        self.defines = join_defines(cpp_info.defines, "-D")
        self.compile_definitions = join_defines(cpp_info.defines)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cxxflags_list = join_flags(";", cpp_info.cxxflags)
        self.cflags_list = join_flags(";", cpp_info.cflags)
        self.sharedlinkflags_list = join_flags(";", format_link_flags(cpp_info.sharedlinkflags))
        self.exelinkflags_list = join_flags(";", format_link_flags(cpp_info.exelinkflags))

        self.rootpath = join_paths([cpp_info.rootpath])
        self.build_modules_paths = join_paths(cpp_info.build_modules_paths.get(generator_name, []))


class CMakeDeps(object):
    name = "CMakeDeps"

    config_template = textwrap.dedent("""
        include(${{CMAKE_CURRENT_LIST_DIR}}/cmakedeps_macros.cmake)

        # Requires CMake > 3.15
        if(${{CMAKE_VERSION}} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${{CMAKE_CURRENT_LIST_DIR}}/{filename}Targets.cmake)

        {target_props_block}
        {build_modules_block}
        {find_dependencies_block}
        """)

    targets_template = textwrap.dedent("""
        if(NOT TARGET {name}::{name})
            add_library({name}::{name} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB DATA_FILES "${{_DIR}}/{filename}-*-data.cmake")

        foreach(f ${{DATA_FILES}})
            include(${{f}})
        endforeach()

        file(GLOB CONFIG_FILES "${{_DIR}}/{filename}Target-*.cmake")
        foreach(f ${{CONFIG_FILES}})
            include(${{f}})
        endforeach()
        """)

    # This template takes the "name" of the target name::name and configs = ["Release", "Debug"..]
    target_properties = Template("""
# Assign target properties
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_LINK_LIBRARIES
             {%- for config in configs %}
             $<$<CONFIG:{{config}}>:${{'{'}}{{name}}_LIBRARIES_TARGETS_{{config.upper()}}}
                                    ${{'{'}}{{name}}_LINKER_FLAGS_{{config.upper()}}}>
             {%- endfor %})
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_INCLUDE_DIRECTORIES
             {%- for config in configs %}
             $<$<CONFIG:{{config}}>:${{'{'}}{{name}}_INCLUDE_DIRS_{{config.upper()}}}>
             {%- endfor %})
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_COMPILE_DEFINITIONS
             {%- for config in configs %}
             $<$<CONFIG:{{config}}>:${{'{'}}{{name}}_COMPILE_DEFINITIONS_{{config.upper()}}}>
             {%- endfor %})
set_property(TARGET {{name}}::{{name}}
             PROPERTY INTERFACE_COMPILE_OPTIONS
             {%- for config in configs %}
             $<$<CONFIG:{{config}}>:${{'{'}}{{name}}_COMPILE_OPTIONS_{{config.upper()}}}>
             {%- endfor %})
    """)

    build_modules = Template("""
# Build modules
{%- for config in configs %}
foreach(_BUILD_MODULE_PATH {{ '${'+name+'_BUILD_MODULES_PATHS_'+config.upper()+'}' }})
    include(${_BUILD_MODULE_PATH})
endforeach()
{%- endfor %}
    """)

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

    components_variables_tpl = Template(textwrap.dedent("""\
        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_variables }}
        set({{ pkg_name }}_COMPONENTS_{{ build_type }} {{ pkg_components }})

        {%- for comp_name, comp in components %}

        ########### COMPONENT {{ comp_name }} VARIABLES #############################################

        set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS_{{ build_type }} {{ comp.include_paths }})
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
        set({{ pkg_name }}_{{ comp_name }}_LINKER_FLAGS_{{ build_type }}
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{ comp.sharedlinkflags_list }}>
                $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{ comp.exelinkflags_list }}>
        )
        {%- endfor %}
    """))

    components_dynamic_variables_tpl = Template(textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        include(${CMAKE_CURRENT_LIST_DIR}/cmakedeps_macros.cmake)

        ########### VARIABLES #######################################################################
        #############################################################################################

        {{ global_dynamic_variables }}

        {%- for comp_name, comp in components %}

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

        # Load the debug and release variables
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB DATA_FILES "${_DIR}/{{ pkg_filename }}-*-data.cmake")

        foreach(f ${DATA_FILES})
            include(${f})
        endforeach()

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
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ pkg_filename }}Targets.cmake)

        ########## FIND PACKAGE DEPENDENCY ##########################################################
        #############################################################################################

        include(CMakeFindDependencyMacro)

        {%- for public_dep in pkg_public_deps %}

        if(NOT {{ public_dep }}_FOUND)
            find_dependency({{ public_dep }} REQUIRED NO_MODULE)
        endif()

        {%- endfor %}

        ########## TARGETS PROPERTIES ###############################################################
        #############################################################################################
        {%- macro tvalue(pkg_name, comp_name, var, config) -%}
        {{'${'+pkg_name+'_'+comp_name+'_'+var+'_'+config.upper()+'}'}}
        {%- endmacro -%}

        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} TARGET PROPERTIES ######################################

        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_LINK_LIBRARIES
                     {%- for config in configs %}
                     $<$<CONFIG:{{config}}>:{{tvalue(pkg_name, comp_name, 'LINK_LIBS', config)}}
                        {{tvalue(pkg_name, comp_name, 'LINKER_FLAGS', config)}}>
                     {%- endfor %})
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     {%- for config in configs %}
                     $<$<CONFIG:{{config}}>:{{tvalue(pkg_name, comp_name, 'INCLUDE_DIRS', config)}}>
                     {%- endfor %})
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     {%- for config in configs %}
                     $<$<CONFIG:{{config}}>:{{tvalue(pkg_name, comp_name, 'COMPILE_DEFINITIONS', config)}}>
                     {%- endfor %})
        set_property(TARGET {{ pkg_name }}::{{ comp_name }} PROPERTY INTERFACE_COMPILE_OPTIONS
                     {%- for config in configs %}
                     $<$<CONFIG:{{config}}>:
                         {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_C', config)}}
                         {{tvalue(pkg_name, comp_name, 'COMPILE_OPTIONS_CXX', config)}}>
                     {%- endfor %})
        set({{ pkg_name }}_{{ comp_name }}_TARGET_PROPERTIES TRUE)

        {%- endfor %}

        ########## GLOBAL TARGET PROPERTIES #########################################################

        if(NOT {{ pkg_name }}_{{ pkg_name }}_TARGET_PROPERTIES)
            set_property(TARGET {{ pkg_name }}::{{ pkg_name }} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                         {%- for config in configs %}
                         $<$<CONFIG:{{config}}>:{{ '${'+pkg_name+'_COMPONENTS_'+config.upper()+'}'}}>
                         {%- endfor %})
        endif()

        ########## BUILD MODULES ####################################################################
        #############################################################################################

        {%- for comp_name, comp in components %}

        ########## COMPONENT {{ comp_name }} BUILD MODULES ##########################################

        {%- for config in configs %}

        foreach(_BUILD_MODULE_PATH {{ '${'+pkg_name+'_'+comp_name+'_BUILD_MODULES_PATHS_'+config.upper()+'}' }})
            include(${_BUILD_MODULE_PATH})
        endforeach()
        {%- endfor %}

        {%- endfor %}
        """))

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.arch = self._conanfile.settings.get_safe("arch")
        self.configuration = str(self._conanfile.settings.build_type)
        self.configurations = [v for v in conanfile.settings.build_type.values_range if v != "None"]
        # FIXME: Ugly way to define the output path
        self.output_path = os.getcwd()

    def _validate_components(self, cpp_info):
        """ Check that all required components are provided by the dependencies """

        def _check_component_in_requirements(require):
            if COMPONENT_SCOPE in require:
                req_name, req_comp_name = require.split(COMPONENT_SCOPE)
                if req_name == req_comp_name:
                    return
                if req_comp_name not in self._conanfile.deps_cpp_info[req_name].components:
                    raise ConanException("Component '%s' not found in '%s' package requirement"
                                         % (require, req_name))

        for comp_name, comp in cpp_info.components.items():
            for cmp_require in comp.requires:
                _check_component_in_requirements(cmp_require)

        for pkg_require in cpp_info.requires:
            _check_component_in_requirements(pkg_require)

    def _get_name(self, cpp_info, pkg_name):
        # FIXME: This is a workaround to be able to use existing recipes that declare
        # FIXME: cpp_info.names["cmake_find_package_multi"] = "xxxxx"
        name = cpp_info.names.get(self.name)
        if name is not None:
            return name
        find_name = cpp_info.names.get("cmake_find_package_multi")
        if find_name is not None:
            # Not displaying a warning, too noisy as this is called many times
            conan_v2_error("'{}' defines information for 'cmake_find_package_multi', "
                           "but not 'CMakeDeps'".format(pkg_name))
            return find_name
        return cpp_info._name

    def _get_filename(self, cpp_info, pkg_name):
        # FIXME: This is a workaround to be able to use existing recipes that declare
        # FIXME: cpp_info.filenames["cmake_find_package_multi"] = "xxxxx"
        name = cpp_info.filenames.get(self.name)
        if name is not None:
            return name
        find_name = cpp_info.filenames.get("cmake_find_package_multi")
        if find_name is not None:
            # Not displaying a warning, too noisy as this is called many times
            conan_v2_error("'{}' defines information for 'cmake_find_package_multi', "
                           "but not 'CMakeDeps'".format(pkg_name))
            return find_name
        return cpp_info._name

    def _get_require_name(self, pkg_name, req):
        pkg, cmp = req.split(COMPONENT_SCOPE) if COMPONENT_SCOPE in req else (pkg_name, req)
        pkg_cpp_info = self._conanfile.deps_cpp_info[pkg]
        pkg_name = self._get_name(pkg_cpp_info, pkg_name)
        if cmp in pkg_cpp_info.components:
            cmp_name = self._get_name(pkg_cpp_info.components[cmp], pkg_name)
        else:
            cmp_name = pkg_name
        return pkg_name, cmp_name

    def _get_components(self, pkg_name, cpp_info):
        ret = []
        sorted_comps = cpp_info._get_sorted_components()

        for comp_name, comp in sorted_comps.items():
            comp_genname = self._get_name(cpp_info.components[comp_name], pkg_name)
            comp_requires_gennames = []
            for require in comp.requires:
                comp_requires_gennames.append(self._get_require_name(pkg_name, require))
            ret.append((comp_genname, comp, comp_requires_gennames))
        ret.reverse()

        result = []
        for comp_genname, comp, comp_requires_gennames in ret:
            deps_cpp_cmake = DepsCppCmake(comp, self.name)
            deps_cpp_cmake.public_deps = " ".join(
                ["{}::{}".format(*it) for it in comp_requires_gennames])
            result.append((comp_genname, deps_cpp_cmake))
        return result

    @classmethod
    def get_public_deps(cls, cpp_info):
        if cpp_info.requires:
            deps = [it for it in cpp_info.requires if COMPONENT_SCOPE in it]
            return [it.split(COMPONENT_SCOPE) for it in deps]
        else:
            return [(it, it) for it in cpp_info.public_deps]

    def generate(self):
        generator_files = self.content
        for generator_file, content in generator_files.items():
            generator_file = os.path.join(self.output_path, generator_file)
            save(generator_file, content)

    def _data_filename(self, pkg_filename):
        data_fname = "{}-{}".format(pkg_filename, self.configuration.lower())
        if self.arch:
            data_fname += "-{}".format(self.arch)
        data_fname += "-data.cmake"
        return data_fname

    @property
    def content(self):
        ret = {}
        build_type = str(self._conanfile.settings.build_type).upper()
        build_type_suffix = "_{}".format(self.configuration.upper()) if self.configuration else ""
        ret["cmakedeps_macros.cmake"] = "\n".join([
            conan_message,
            apple_frameworks_macro,
            conan_package_library_targets,
        ])

        for pkg_name, cpp_info in self._conanfile.deps_cpp_info.dependencies:
            self._validate_components(cpp_info)
            pkg_filename = self._get_filename(cpp_info, pkg_name)
            pkg_findname = self._get_name(cpp_info, pkg_name)
            pkg_version = cpp_info.version

            public_deps = self.get_public_deps(cpp_info)
            deps_names = []
            for it in public_deps:
                name = "{}::{}".format(*self._get_require_name(*it))
                if name not in deps_names:
                    deps_names.append(name)
            deps_names = ';'.join(deps_names)
            pkg_public_deps_filenames = [self._get_filename(self._conanfile.deps_cpp_info[it[0]],
                                                            pkg_name)
                                         for it in public_deps]
            config_version = self.config_version_template.format(version=pkg_version)
            ret[self._config_version_filename(pkg_filename)] = config_version
            if not cpp_info.components:
                # If any config matches the build_type one, add it to the cpp_info
                dep_cpp_info = extend(cpp_info, build_type.lower())
                deps = DepsCppCmake(dep_cpp_info, self.name)

                variables = {
                   self._data_filename(pkg_filename):
                       variables_template.format(name=pkg_findname, deps=deps,
                                                 build_type_suffix=build_type_suffix)
                             }
                dynamic_variables = {
                    "{}Target-{}.cmake".format(pkg_filename, self.configuration.lower()):
                    dynamic_variables_template.format(name=pkg_findname,
                                                      build_type_suffix=build_type_suffix,
                                                      deps_names=deps_names)
                }
                ret.update(variables)
                ret.update(dynamic_variables)
                ret[self._config_filename(pkg_filename)] = self._config(
                    filename=pkg_filename,
                    name=pkg_findname,
                    version=cpp_info.version,
                    public_deps_names=pkg_public_deps_filenames
                )
                ret["{}Targets.cmake".format(pkg_filename)] = self.targets_template.format(
                    filename=pkg_filename, name=pkg_findname)
            else:
                cpp_info = extend(cpp_info, build_type.lower())
                pkg_info = DepsCppCmake(cpp_info, self.name)
                components = self._get_components(pkg_name, cpp_info)
                # Note these are in reversed order, from more dependent to less dependent
                pkg_components = " ".join(["{p}::{c}".format(p=pkg_findname, c=comp_findname) for
                                           comp_findname, _ in reversed(components)])
                global_variables = variables_template.format(name=pkg_findname, deps=pkg_info,
                                                             build_type_suffix=build_type_suffix,
                                                             deps_names=deps_names)
                variables = {
                    self._data_filename(pkg_filename):
                        self.components_variables_tpl.render(
                         pkg_name=pkg_findname, global_variables=global_variables,
                         pkg_components=pkg_components, build_type=build_type, components=components)
                }
                ret.update(variables)
                global_dynamic_variables = dynamic_variables_template.format(name=pkg_findname,
                                                                             build_type_suffix=build_type_suffix,
                                                                             deps_names=deps_names)
                dynamic_variables = {
                    "{}Target-{}.cmake".format(pkg_filename, build_type.lower()):
                    self.components_dynamic_variables_tpl.render(
                        pkg_name=pkg_findname, global_dynamic_variables=global_dynamic_variables,
                        pkg_components=pkg_components, build_type=build_type, components=components)
                }
                ret.update(dynamic_variables)
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
                    configs=self.configurations
                )
                ret[self._config_filename(pkg_filename)] = target_config
        return ret

    @staticmethod
    def _config_filename(pkg_filename):
        if pkg_filename == pkg_filename.lower():
            return "{}-config.cmake".format(pkg_filename)
        else:
            return "{}Config.cmake".format(pkg_filename)

    @staticmethod
    def _config_version_filename(pkg_filename):
        if pkg_filename == pkg_filename.lower():
            return "{}-config-version.cmake".format(pkg_filename)
        else:
            return "{}ConfigVersion.cmake".format(pkg_filename)

    def _config(self, filename, name, version, public_deps_names):
        # Builds the XXXConfig.cmake file for one package
        # Define the targets properties
        targets_props = self.target_properties.render(name=name, configs=self.configurations)
        # Add build modules
        build_modules_block = self.build_modules.render(name=name, configs=self.configurations)
        # The find_dependencies_block
        find_dependencies_block = ""
        if public_deps_names:
            # Here we are generating only Config files, so do not search for FindXXX modules
            find_dependencies_block = find_transitive_dependencies(public_deps_names)

        tmp = self.config_template.format(name=name, version=version,
                                          filename=filename,
                                          target_props_block=targets_props,
                                          build_modules_block=build_modules_block,
                                          find_dependencies_block=find_dependencies_block)
        return tmp
