import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooConfig.cmake
foo-config.cmake

"""


class ConfigTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        if self.generating_module:
            return "Find{}.cmake".format(self.file_name)
        else:
            if self.file_name == self.file_name.lower():
                return "{}-config.cmake".format(self.file_name)
            else:
                return "{}Config.cmake".format(self.file_name)

    @property
    def context(self):
        targets_include = "" if not self.generating_module else "module-"
        targets_include += "{}Targets.cmake".format(self.file_name)
        return {"is_module": self.generating_module,
                "version": self.conanfile.ref.version,
                "file_name": self.file_name,
                "pkg_name": self.pkg_name,
                "config_suffix": self.config_suffix,
                "check_components_exist": self.cmakedeps.check_components_exist,
                "targets_include_file": targets_include}

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
        include(${CMAKE_CURRENT_LIST_DIR}/{{ targets_include_file }})
        include(CMakeFindDependencyMacro)

        check_build_type_defined()

        foreach(_DEPENDENCY {{ '${' + pkg_name + '_FIND_DEPENDENCY_NAMES' + '}' }} )
            # Check that we have not already called a find_package with the transitive dependency
            if(NOT {{ '${_DEPENDENCY}' }}_FOUND)
                find_dependency({{ '${_DEPENDENCY}' }} REQUIRED ${${_DEPENDENCY}_FIND_MODE})
            endif()
        endforeach()

        set({{ file_name }}_VERSION_STRING "{{ version }}")
        set({{ file_name }}_INCLUDE_DIRS {{ '${' + pkg_name + '_INCLUDE_DIRS' + config_suffix + '}' }} )
        set({{ file_name }}_INCLUDE_DIR {{ '${' + pkg_name + '_INCLUDE_DIRS' + config_suffix + '}' }} )
        set({{ file_name }}_LIBRARIES {{ '${' + pkg_name + '_LIBRARIES' + config_suffix + '}' }} )
        set({{ file_name }}_DEFINITIONS {{ '${' + pkg_name + '_DEFINITIONS' + config_suffix + '}' }} )

        # Only the first installed configuration is included to avoid the collision
        foreach(_BUILD_MODULE {{ '${' + pkg_name + '_BUILD_MODULES_PATHS' + config_suffix + '}' }} )
            message(STATUS "Conan: Including build module from '${_BUILD_MODULE}'")
            include({{ '${_BUILD_MODULE}' }})
        endforeach()

        {% if check_components_exist %}
        # Check that the specified components in the find_package(Foo COMPONENTS x y z) are there
        # This is the variable filled by CMake with the requested components in find_package
        if({{ file_name }}_FIND_COMPONENTS)
            foreach(_FIND_COMPONENT {{ '${'+file_name+'_FIND_COMPONENTS}' }})
                if (TARGET ${_FIND_COMPONENT})
                    message(STATUS "Conan: Component '${_FIND_COMPONENT}' found in package '{{ pkg_name }}'")
                else()
                    message(FATAL_ERROR "Conan: Component '${_FIND_COMPONENT}' NOT found in package '{{ pkg_name }}'")
                endif()
            endforeach()
        endif()
        {% endif %}

        {% if is_module %}
        include(FindPackageHandleStandardArgs)
        set({{ file_name }}_FOUND 1)
        set({{ file_name }}_VERSION "{{ version }}")

        find_package_handle_standard_args({{ file_name }}
                                          REQUIRED_VARS {{ file_name }}_VERSION
                                          VERSION_VAR {{ file_name }}_VERSION)
        mark_as_advanced({{ file_name }}_FOUND {{ file_name }}_VERSION)
        {% endif %}
        """)
