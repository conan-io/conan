import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

cmakedeps_macros.cmake

"""


class MacrosTemplate(CMakeDepsFileTemplate):
    """cmakedeps_macros.cmake"""

    def __init__(self):
        super(MacrosTemplate, self).__init__(cmakedeps=None, require=None, conanfile=None)

    @property
    def filename(self):
        return "cmakedeps_macros.cmake"

    @property
    def context(self):
        return {}

    @property
    def template(self):
        return textwrap.dedent("""
        function(conan_message type message)
            if(NOT CONAN_CMAKE_SILENT_OUTPUT)
                message(${type} "Conan:" "${message}" ${ARGN})
            endif()
        endfunction()

        function(conan_determine_windows_library_type library_path out_type)
            set(${out_type} UNKNOWN PARENT_SCOPE)

            if(EXISTS "${library_path}")
                if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20.0)
                    cmake_path(GET library_path EXTENSION ext)
                    cmake_path(GET library_path STEM name)
                else()
                    get_filename_component(ext "${library_path}" EXT)
                    get_filename_component(name "${library_path}" NAME_WE)
                endif()

                # Is the .lib file a dynamic library.
                file(STRINGS "${library_path}" match REGEX "${name}\\.[dll|DLL]" LIMIT_COUNT 1)
                if(NOT match STREQUAL "")
                    set(${out_type} SHARED PARENT_SCOPE)
                endif()
            endif()
        endfunction()

        function(conan_determine_unix_library_type library_path out_type)
            set(${out_type} UNKNOWN PARENT_SCOPE)
            if(EXISTS "${library_path}")
                if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20.0)
                    cmake_path(GET library_path EXTENSION ext)
                else()
                    get_filename_component(ext "${library_path}" EXT)
                endif()

                # Does it match a common Unix library extension.
                # - A.so.1.3.0, A.so, A.dylib, A.dylib.1.3.0
                if(ext MATCHES ".*\\.(a)(\\..+)$")
                    set(${out_type} STATIC PARENT_SCOPE)
                elseif(ext MATCHES ".*\\.(so|dylib)(\\..+)$")
                    set(${out_type} SHARED PARENT_SCOPE)
                endif()
            endif()
        endfunction()

        function(conan_determine_library_type library_path out_type)
            set(type UNKNOWN)
            if(WIN32)
                conan_determine_windows_library_type(${library_path} type)
            else(UNIX)
                conan_determine_unix_library_type(${library_path} type)
            endif()

            set(${out_type} ${type} PARENT_SCOPE)
        endfunction()

        function(conan_define_package_library_target package_bindirs library_name target_name library_path)

            conan_determine_library_type(library_path type)
            add_library(${target_name} ${type} IMPORTED)

            set(imported_loc)
            set(imported_imp_lib)
            if(WIN32)
                if(type STREQUAL "SHARED")
                    # Find a corresponding DLL in the binary directory (if possible)
                    # We search for the exact same name but with a .DLL/.dll ending
                    # inside the package bin directory.
                    if(CMAKE_VERSION VERSION_GREATER_EQUAL 3.20.0)
                        cmake_path(GET library_path FILENAME name)
                    else()
                        get_filename_component(name "${library_path}" NAME)
                    endif()

                    string(REPLACE ".lib" ".dll" runtimeLib1 "${name}")
                    string(REPLACE ".lib" ".DLL" runtimeLib2 "${name}")

                    foreach(runtimeLib IN ITEMS "${runtimeLib1}" "${runtimeLib2}")
                        find_file(found NAMES "${runtimeLib}" PATHS ${package_bindirs}
                                  NO_DEFAULT_PATH
                                  NO_PACKAGE_ROOT_PATH
                                  NO_CMAKE_PATH
                                  NO_CMAKE_ENVIRONMENT_PATH
                                  NO_CMAKE_SYSTEM_PATH
                                  NO_CMAKE_FIND_ROOT_PATH
                                  NO_CACHE)
                        if(found)
                            set(imported_imp_lib ${library_path})
                            set(imported_loc ${found})
                            conan_message(DEBUG "Runtime Library ${library_name} found '${found}'")
                            break()
                        endif()
                    endforeach()
                else()
                    set(imported_loc ${library_path})
                endif()
            else(UNIX)
                set(imported_loc ${library_path})
            endif()

            # Set the libraries.
            set_target_properties(${target} PROPERTIES IMPORTED_LOCATION ${imported_loc})
            if(NOT imported_imp_lib STREQUAL "")
                set_target_properties(${target} PROPERTIES IMPORTED_LOCATION ${imported_imp_lib})
            endif()

        endfunction()

        macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
            if(APPLE)
                foreach(_FRAMEWORK ${FRAMEWORKS})
                    # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                    find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAMES ${_FRAMEWORK}
                                PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
                    if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                        list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                        conan_message(DEBUG "Framework found! ${FRAMEWORKS_FOUND}")
                    else()
                        conan_message(FATAL_ERROR "Framework library ${_FRAMEWORK} "
                                    "not found in paths: ${FRAMEWORKS_DIRS}")
                    endif()
                endforeach()
            endif()
        endmacro()

        function(conan_package_library_targets
                 libraries
                 package_bindirs
                 package_libdirs
                 deps
                 out_libraries
                 out_libraries_target
                 config_suffix
                 package_name)

            set(_out_libraries "")
            set(_out_libraries_target "")
            set(_actual_targets "")

            foreach(library_name ${libraries})

                find_library(CONAN_FOUND_LIBRARY NAMES ${library_name} PATHS ${package_libdirs}
                             NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH NO_CACHE)

                if(CONAN_FOUND_LIBRARY)
                    conan_message(DEBUG "Library ${library_name} found '${CONAN_FOUND_LIBRARY}'")
                    list(APPEND _out_libraries ${CONAN_FOUND_LIBRARY})

                    # Create a micro-target for each lib/a found
                    # Allow only some characters for the target name
                    string(REGEX REPLACE "[^A-Za-z0-9.+_-]" "_" library_name ${library_name})
                    set(target_name CONAN_LIB::${package_name}_${library_name}${config_suffix})
                    if(NOT TARGET ${target_name})
                        # Create a micro-target for each lib/a found
                        conan_define_package_library_target("${package_bindirs}" ${library_name} ${target_name} ${CONAN_FOUND_LIBRARY})
                        list(APPEND _actual_targets ${target_name})
                    else()
                        conan_message(STATUS "Skipping already existing target: '${target_name}'")
                    endif()
                    list(APPEND _out_libraries_target ${target_name})
                    conan_message(DEBUG "Found: ${CONAN_FOUND_LIBRARY}")
                else()
                    conan_message(FATAL_ERROR "Library '${library_name}' not found in package. If '${library_name}' is a "
                                "system library, declare it with 'cpp_info.system_libs' property")
                endif()
            endforeach()

            # Add all dependencies to all targets
            string(REPLACE " " ";" deps_list "${deps}")
            foreach(target IN LISTS _actual_targets)
                set_property(TARGET ${target} PROPERTY INTERFACE_LINK_LIBRARIES "${deps_list}" APPEND)
            endforeach()

            set(${out_libraries} ${_out_libraries} PARENT_SCOPE)
            set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
        endfunction()
        """)
