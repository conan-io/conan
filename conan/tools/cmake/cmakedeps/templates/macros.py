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
        function(conan_message MESSAGE_TYPE MESSAGE_CONTENT)
            if(NOT CONAN_CMAKE_SILENT_OUTPUT)
                message(${MESSAGE_TYPE} "${MESSAGE_CONTENT}")
            endif()
        endfunction()

       macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS FRAMEWORKS_DIRS)
           if(APPLE)
               foreach(_FRAMEWORK ${FRAMEWORKS})
                   # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                   find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAMES ${_FRAMEWORK} PATHS ${FRAMEWORKS_DIRS} CMAKE_FIND_ROOT_PATH_BOTH)
                   if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                       list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                       conan_message(DEBUG "Framework found! ${FRAMEWORKS_FOUND}")
                   else()
                       conan_message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${FRAMEWORKS_DIRS}")
                   endif()
               endforeach()
           endif()
       endmacro()

       function(conan_package_library_targets libraries_vars_names package_libdir deps out_libraries_target config_suffix package_name)
           set(_out_libraries_target "")
           set(_CONAN_ACTUAL_TARGETS "")

           foreach(_LIBRARY_VAR_NAME ${libraries_vars_names})
               if(NOT TARGET ${_LIBRARY_VAR_NAME})
                   # Create a micro-target for each lib/a found
                   set(_LIB_TYPE ${${package_name}_LIB_${_LIBRARY_VAR_NAME}_TYPE${config_suffix}})
                   set(_REAL_PATH ${${package_name}_LIB_${_LIBRARY_VAR_NAME}_REAL_PATH${config_suffix}})
                   add_library(${_LIBRARY_VAR_NAME} ${_LIB_TYPE} IMPORTED)
                   set_target_properties(${_LIBRARY_VAR_NAME} PROPERTIES IMPORTED_LOCATION "${_REAL_PATH}")
                   list(APPEND _CONAN_ACTUAL_TARGETS ${_LIBRARY_VAR_NAME})
               else()
                   conan_message(STATUS "Skipping already existing target: ${_LIBRARY_VAR_NAME}")
               endif()
               list(APPEND _out_libraries_target ${_LIBRARY_VAR_NAME})
           endforeach()

           # Add all dependencies to all targets
           string(REPLACE " " ";" deps_list "${deps}")
           foreach(_CONAN_ACTUAL_TARGET ${_CONAN_ACTUAL_TARGETS})
               set_property(TARGET ${_CONAN_ACTUAL_TARGET} PROPERTY INTERFACE_LINK_LIBRARIES "${deps_list}" APPEND)
           endforeach()

           set(${out_libraries_target} ${_out_libraries_target} PARENT_SCOPE)
       endfunction()
        """)
