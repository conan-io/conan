import textwrap

target_template = """
set({name}_INCLUDE_DIRS{build_type_suffix} {deps.include_paths})
set({name}_INCLUDE_DIR{build_type_suffix} {deps.include_path})
set({name}_INCLUDES{build_type_suffix} {deps.include_paths})
set({name}_RES_DIRS{build_type_suffix} {deps.res_paths})
set({name}_DEFINITIONS{build_type_suffix} {deps.defines})
set({name}_LINKER_FLAGS{build_type_suffix}_LIST "{deps.sharedlinkflags_list}" "{deps.exelinkflags_list}")
set({name}_COMPILE_DEFINITIONS{build_type_suffix} {deps.compile_definitions})
set({name}_COMPILE_OPTIONS{build_type_suffix}_LIST "{deps.cxxflags_list}" "{deps.cflags_list}")
set({name}_LIBRARIES_TARGETS{build_type_suffix} "") # Will be filled later, if CMake 3
set({name}_LIBRARIES{build_type_suffix} "") # Will be filled later
set({name}_LIBS{build_type_suffix} "") # Same as {name}_LIBRARIES
set({name}_SYSTEM_LIBS{build_type_suffix} {deps.system_libs})
set({name}_FRAMEWORK_DIRS{build_type_suffix} {deps.framework_paths})
set({name}_FRAMEWORKS{build_type_suffix} {deps.frameworks})
set({name}_FRAMEWORKS_FOUND{build_type_suffix} "") # Will be filled later
set({name}_BUILD_MODULES_PATHS{build_type_suffix} {deps.build_modules_paths})

conan_find_apple_frameworks({name}_FRAMEWORKS_FOUND{build_type_suffix} "${{{name}_FRAMEWORKS{build_type_suffix}}}")

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
foreach(_LIBRARY_NAME ${{{name}_LIBRARY_LIST{build_type_suffix}}})
    unset(CONAN_FOUND_LIBRARY CACHE)
    find_library(CONAN_FOUND_LIBRARY NAME ${{_LIBRARY_NAME}} PATHS ${{{name}_LIB_DIRS{build_type_suffix}}}
                 NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
    if(CONAN_FOUND_LIBRARY)
        list(APPEND {name}_LIBRARIES{build_type_suffix} ${{CONAN_FOUND_LIBRARY}})
        if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
            # Create a micro-target for each lib/a found
            set(_LIB_NAME CONAN_LIB::{name}_${{_LIBRARY_NAME}}{build_type_suffix})
            if(NOT TARGET ${{_LIB_NAME}})
                # Create a micro-target for each lib/a found
                add_library(${{_LIB_NAME}} UNKNOWN IMPORTED)
                set_target_properties(${{_LIB_NAME}} PROPERTIES IMPORTED_LOCATION ${{CONAN_FOUND_LIBRARY}})
            else()
                message(STATUS "Skipping already existing target: ${{_LIB_NAME}}")
            endif()
            list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_LIB_NAME}})
        endif()
        message(STATUS "Found: ${{CONAN_FOUND_LIBRARY}}")
    else()
        message(STATUS "Library ${{_LIBRARY_NAME}} not found in package, might be system one")
        list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_LIBRARY_NAME}})
        list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_LIBRARY_NAME}})
    endif()
endforeach()
set({name}_LIBS{build_type_suffix} ${{{name}_LIBRARIES{build_type_suffix}}})

foreach(_FRAMEWORK ${{{name}_FRAMEWORKS_FOUND{build_type_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_FRAMEWORK}})
    list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_FRAMEWORK}})
endforeach()

foreach(_SYSTEM_LIB ${{{name}_SYSTEM_LIB{build_type_suffix}}})
    list(APPEND {name}_LIBRARIES_TARGETS{build_type_suffix} ${{_SYSTEM_LIB}})
    list(APPEND {name}_LIBRARIES{build_type_suffix} ${{_SYSTEM_LIB}})
endforeach()

set(CMAKE_MODULE_PATH {deps.build_paths} ${{CMAKE_MODULE_PATH}})
set(CMAKE_PREFIX_PATH {deps.build_paths} ${{CMAKE_PREFIX_PATH}})

foreach(_BUILD_MODULE_PATH ${{{name}_BUILD_MODULES_PATHS{build_type_suffix}}})
    include(${{_BUILD_MODULE_PATH}})
endforeach()
"""


class CMakeFindPackageCommonMacros:
    apple_frameworks_macro = textwrap.dedent("""
        macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS)
            if(APPLE)
                foreach(_FRAMEWORK ${FRAMEWORKS})
                    # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                    find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAME ${_FRAMEWORK} PATHS ${CONAN_FRAMEWORK_DIRS})
                    if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                        list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                    else()
                        message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${CONAN_FRAMEWORK_DIRS}")
                    endif()
                endforeach()
            endif()
        endmacro()
    """)

    conan_package_library_targets = textwrap.dedent("""
        function(conan_package_library_targets libraries package_libdir libraries_abs_path deps build_type package_name)
            foreach(_LIBRARY_NAME ${libraries})
                unset(CONAN_FOUND_LIBRARY CACHE)
                find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir}
                             NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
                if(CONAN_FOUND_LIBRARY)
                    conan_message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
                    
                    set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${build_type})
                    add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                    set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                    string(REPLACE " " ";" deps_list "${deps}")
                    set_property(TARGET ${_LIB_NAME} PROPERTY INTERFACE_LINK_LIBRARIES ${deps_list})
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIB_NAME})
                else()
                    conan_message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
                    
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
                endif()
            endforeach()
            unset(CONAN_FOUND_LIBRARY CACHE)
            set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
        endfunction()
    """)
