import textwrap

from conans.client.generators.cmake_common import CMakeCommonMacros

target_template = """
set({name}_INCLUDE_DIRS{build_type_suffix} {deps.include_paths})
set({name}_INCLUDE_DIR{build_type_suffix} {deps.include_path})
set({name}_INCLUDES{build_type_suffix} {deps.include_paths})
set({name}_RES_DIRS{build_type_suffix} {deps.res_paths})
set({name}_DEFINITIONS{build_type_suffix} {deps.defines})
set({name}_LINKER_FLAGS{build_type_suffix}_LIST
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{deps.sharedlinkflags_list}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{deps.sharedlinkflags_list}>"
        "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{deps.exelinkflags_list}>"
)
set({name}_COMPILE_DEFINITIONS{build_type_suffix} {deps.compile_definitions})
set({name}_COMPILE_OPTIONS{build_type_suffix}_LIST "{deps.cxxflags_list}" "{deps.cflags_list}")
set({name}_COMPILE_OPTIONS_C{build_type_suffix} "{deps.cflags_list}")
set({name}_COMPILE_OPTIONS_CXX{build_type_suffix} "{deps.cxxflags_list}")
set({name}_LIBRARIES_TARGETS{build_type_suffix} "") # Will be filled later, if CMake 3
set({name}_LIBRARIES{build_type_suffix} "") # Will be filled later
set({name}_LIBS{build_type_suffix} "") # Same as {name}_LIBRARIES
set({name}_SYSTEM_LIBS{build_type_suffix} {deps.system_libs})
set({name}_FRAMEWORK_DIRS{build_type_suffix} {deps.framework_paths})
set({name}_FRAMEWORKS{build_type_suffix} {deps.frameworks})
set({name}_FRAMEWORKS_FOUND{build_type_suffix} "") # Will be filled later
set({name}_BUILD_MODULES_PATHS{build_type_suffix} {deps.build_modules_paths})

conan_find_apple_frameworks({name}_FRAMEWORKS_FOUND{build_type_suffix} "${{{name}_FRAMEWORKS{build_type_suffix}}}" "${{{name}_FRAMEWORK_DIRS{build_type_suffix}}}")

mark_as_advanced({name}_INCLUDE_DIRS{build_type_suffix}
                 {name}_INCLUDE_DIR{build_type_suffix}
                 {name}_INCLUDES{build_type_suffix}
                 {name}_DEFINITIONS{build_type_suffix}
                 {name}_LINKER_FLAGS{build_type_suffix}_LIST
                 {name}_COMPILE_DEFINITIONS{build_type_suffix}
                 {name}_COMPILE_OPTIONS{build_type_suffix}_LIST
                 {name}_LIBRARIES{build_type_suffix}
                 {name}_LIBS{build_type_suffix}
                 {name}_LIBRARIES_TARGETS{build_type_suffix})

# Find the real .lib/.a and add them to {name}_LIBS and {name}_LIBRARY_LIST
set({name}_LIBRARY_LIST{build_type_suffix} {deps.libs})
set({name}_LIB_DIRS{build_type_suffix} {deps.lib_paths})

# Gather all the libraries that should be linked to the targets (do not touch existing variables):
set(_{name}_DEPENDENCIES{build_type_suffix} "${{{name}_FRAMEWORKS_FOUND{build_type_suffix}}} ${{{name}_SYSTEM_LIBS{build_type_suffix}}} {deps_names}")

conan_package_library_targets("${{{name}_LIBRARY_LIST{build_type_suffix}}}"  # libraries
                              "${{{name}_LIB_DIRS{build_type_suffix}}}"      # package_libdir
                              "${{_{name}_DEPENDENCIES{build_type_suffix}}}"  # deps
                              {name}_LIBRARIES{build_type_suffix}            # out_libraries
                              {name}_LIBRARIES_TARGETS{build_type_suffix}    # out_libraries_targets
                              "{build_type_suffix}"                          # build_type
                              "{name}")                                      # package_name

set({name}_LIBS{build_type_suffix} ${{{name}_LIBRARIES{build_type_suffix}}})

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

set(CMAKE_MODULE_PATH {deps.build_paths} ${{CMAKE_MODULE_PATH}})
set(CMAKE_PREFIX_PATH {deps.build_paths} ${{CMAKE_PREFIX_PATH}})

foreach(_BUILD_MODULE_PATH ${{{name}_BUILD_MODULES_PATHS{build_type_suffix}}})
    include(${{_BUILD_MODULE_PATH}})
endforeach()
"""


def find_transitive_dependencies(public_deps_filenames, find_modules):
    if find_modules:  # for cmake_find_package generator
        find = textwrap.dedent("""
            if(NOT {dep_filename}_FOUND)
                find_dependency({dep_filename} REQUIRED)
            else()
                message(STATUS "Dependency {dep_filename} already found")
            endif()
            """)
    else:  # for cmake_find_package_multi generator
        # https://github.com/conan-io/conan/issues/4994
        # https://github.com/conan-io/conan/issues/5040
        find = textwrap.dedent("""
            if(NOT {dep_filename}_FOUND)
                if(${{CMAKE_VERSION}} VERSION_LESS "3.9.0")
                    find_package({dep_filename} REQUIRED NO_MODULE)
                else()
                    find_dependency({dep_filename} REQUIRED NO_MODULE)
                endif()
            else()
                message(STATUS "Dependency {dep_filename} already found")
            endif()
            """)
    lines = ["", "# Library dependencies", "include(CMakeFindDependencyMacro)"]
    for dep_filename in public_deps_filenames:
        lines.append(find.format(dep_filename=dep_filename))
    return "\n".join(lines)


class CMakeFindPackageCommonMacros:
    conan_message = CMakeCommonMacros.conan_message

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
            unset(_CONAN_FOUND_SYSTEM_LIBS CACHE)
            foreach(_LIBRARY_NAME ${libraries})
                find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                             NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
                if(CONAN_FOUND_LIBRARY)
                    conan_message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
                    list(APPEND _out_libraries ${CONAN_FOUND_LIBRARY})
                    if(NOT ${CMAKE_VERSION} VERSION_LESS "3.0")
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
                    endif()
                    conan_message(STATUS "Found: ${CONAN_FOUND_LIBRARY}")
                else()
                    conan_message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
                    list(APPEND _out_libraries_target ${_LIBRARY_NAME})
                    list(APPEND _out_libraries ${_LIBRARY_NAME})
                    set(_CONAN_FOUND_SYSTEM_LIBS "${_CONAN_FOUND_SYSTEM_LIBS};${_LIBRARY_NAME}")
                endif()
                unset(CONAN_FOUND_LIBRARY CACHE)
            endforeach()

            if(NOT ${CMAKE_VERSION} VERSION_LESS "3.0")
                # Add all dependencies to all targets
                string(REPLACE " " ";" deps_list "${deps}")
                foreach(_CONAN_ACTUAL_TARGET ${_CONAN_ACTUAL_TARGETS})
                    set_property(TARGET ${_CONAN_ACTUAL_TARGET} PROPERTY INTERFACE_LINK_LIBRARIES "${_CONAN_FOUND_SYSTEM_LIBS};${deps_list}")
                endforeach()
            endif()

            set(${out_libraries} ${_out_libraries} PARENT_SCOPE)
            set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
        endfunction()
    """)
