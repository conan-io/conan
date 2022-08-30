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
       macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
           if(APPLE)
               foreach(_FRAMEWORK ${FRAMEWORKS})
                   # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                   find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAMES ${_FRAMEWORK} PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
                   if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                       list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                       message(VERBOSE "Framework found! ${FRAMEWORKS_FOUND}")
                   else()
                       message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${FRAMEWORKS_DIRS}")
                   endif()
               endforeach()
           endif()
       endmacro()

       function(conan_package_library_targets libraries package_libdir deps_target out_libraries_target config_suffix package_name)
           set(_out_libraries_target "")

           foreach(_LIBRARY_NAME ${libraries})
               find_library(CONAN_FOUND_LIBRARY NAMES ${_LIBRARY_NAME} PATHS ${package_libdir}
                            NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
               if(CONAN_FOUND_LIBRARY)
                   message(VERBOSE "Conan: Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")

                   # Create a micro-target for each lib/a found
                   # Allow only some characters for the target name
                   string(REGEX REPLACE "[^A-Za-z0-9.+_-]" "_" _LIBRARY_NAME ${_LIBRARY_NAME})
                   set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${config_suffix})
                   if(NOT TARGET ${_LIB_NAME})
                       # Create a micro-target for each lib/a found
                       add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                   endif()
                   # Link library file
                   set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                   list(APPEND _out_libraries_target ${_LIB_NAME})
                   message(VERBOSE "Conan: Found: ${CONAN_FOUND_LIBRARY}")
               else()
                   message(FATAL_ERROR "Library '${_LIBRARY_NAME}' not found in package. If '${_LIBRARY_NAME}' is a system library, declare it with 'cpp_info.system_libs' property")
               endif()
               unset(CONAN_FOUND_LIBRARY CACHE)
           endforeach()

           # Add the dependencies target for all the imported libraries
           foreach(_T ${_out_libraries_target})
               set_property(TARGET ${_T} PROPERTY INTERFACE_LINK_LIBRARIES ${deps_target} APPEND)
           endforeach()

           set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
       endfunction()

       macro(check_build_type_defined)
           # Check that the -DCMAKE_BUILD_TYPE argument is always present
           get_property(isMultiConfig GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
           if(NOT isMultiConfig AND NOT CMAKE_BUILD_TYPE)
               message(FATAL_ERROR "Please, set the CMAKE_BUILD_TYPE variable when calling to CMake "
                                   "adding the '-DCMAKE_BUILD_TYPE=<build_type>' argument.")
           endif()
       endmacro()

        """)
