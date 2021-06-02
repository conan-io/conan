import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooConfig.cmake
foo-config.cmake

"""


class ConfigTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        if self.file_name == self.file_name.lower():
            return "{}-config.cmake".format(self.file_name)
        else:
            return "{}Config.cmake".format(self.file_name)

    @property
    def context(self):
        return {"file_name": self.file_name,
                "pkg_name": self.pkg_name,
                "config_suffix": self.config_suffix}

    @property
    def template(self):
        return textwrap.dedent("""\
        ########## MACROS ###########################################################################
        #############################################################################################
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/cmakedeps_macros.cmake)
        include(${CMAKE_CURRENT_LIST_DIR}/{{ file_name }}Targets.cmake)
        include(CMakeFindDependencyMacro)

        foreach(_DEPENDENCY {{ '${' + pkg_name + '_FIND_DEPENDENCY_NAMES' + '}' }} )
            if(NOT {{ '${_DEPENDENCY}' }}_FOUND)
                find_dependency({{ '${_DEPENDENCY}' }} REQUIRED NO_MODULE)
            endif()
        endforeach()

        # Only the first installed configuration is included to avoid the collission
        foreach(_BUILD_MODULE {{ '${' + pkg_name + '_BUILD_MODULES_PATHS' + config_suffix + '}' }} )
            conan_message(STATUS "Conan: Including build module from '${_BUILD_MODULE}'")
            include({{ '${_BUILD_MODULE}' }})
        endforeach()

        """)
