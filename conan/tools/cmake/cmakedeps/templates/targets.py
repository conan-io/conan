import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooTargets.cmake

"""


class TargetsTemplate(CMakeDepsFileTemplate):

    def __init__(self, req):
        super(TargetsTemplate, self).__init__(req, configuration=None)

    @property
    def filename(self):
        return "{}Targets.cmake".format(self.pkg_name)

    @property
    def context(self):
        ret = {"pkg_name": self.pkg_name,
               "pkg_alias_name": self.get_rename()}
        return ret

    @property
    def template(self):
        return textwrap.dedent("""\
        # Load the debug and release variables
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB DATA_FILES "${_DIR}/{{ pkg_name }}-*-data.cmake")

        foreach(f ${DATA_FILES})
            include(${f})
        endforeach()

        # Create the targets for all the components
        foreach(_COMPONENT {{ '${' + pkg_name + '_COMPONENT_NAMES' + '}' }} )
            if(NOT TARGET {{ pkg_name }}::${_COMPONENT})
                add_library({{ pkg_name }}::${_COMPONENT} INTERFACE IMPORTED)
                set(_COMPONENT_ALIAS {{ '${' + pkg_name + '_${_COMPONENT}_ALIAS}' }})
                conan_message(STATUS "Conan: Target declared '{{ pkg_name }}::${_COMPONENT}'")
                if(NOT "{{pkg_name}}" STREQUAL "{{pkg_alias_name}}")
                    if(TARGET {{ pkg_alias_name }}::${_COMPONENT_ALIAS})
                        conan_message(FATAL_ERROR "Target '{{ pkg_alias_name }}::${_COMPONENT_ALIAS}' already declared!")
                    else()
                        add_library({{ pkg_alias_name }}::${_COMPONENT_ALIAS} ALIAS {{ pkg_name }}::${_COMPONENT})
                        conan_message(STATUS "Target ALIAS declared '{{ pkg_alias_name }}::${_COMPONENT_ALIAS}' (from {{pkg_name}}::${_COMPONENT})")
                    endif()
                endif()
            endif()
        endforeach()

        if(NOT TARGET {{ pkg_name }}::{{ pkg_name }})
            add_library({{ pkg_name }}::{{ pkg_name }} INTERFACE IMPORTED)
            conan_message(STATUS "Conan: Target declared '{{ pkg_name }}::{{ pkg_name }}'")
            # Always keep a target with the unique name of the package in case there is some collision
            if(NOT "{{pkg_name}}" STREQUAL "{{pkg_alias_name}}")
                if(TARGET {{ pkg_alias_name }}::{{ pkg_alias_name }})
                    conan_message(FATAL_ERROR "Target '{{ pkg_alias_name }}::{{ pkg_alias_name }}' already declared!")
                else()
                    add_library({{pkg_alias_name}}::{{pkg_alias_name}} ALIAS {{pkg_name}}::{{pkg_name}})
                    conan_message(STATUS "Target ALIAS declared '{{pkg_alias_name}}::{{pkg_alias_name}}' (from {{pkg_name}}::{{pkg_name}})")
                endif()
            endif()
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB CONFIG_FILES "${_DIR}/{{ pkg_name }}Target-*.cmake")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()

        # This is the variable filled by CMake with the requested components in find_package
        if({{ pkg_name }}_FIND_COMPONENTS)
            foreach(_FIND_COMPONENT {{ '${'+pkg_name+'_FIND_COMPONENTS}' }})
                list(FIND {{ pkg_name }}_COMPONENT_NAMES "${_FIND_COMPONENT}" _index)
                if(${_index} EQUAL -1)
                    conan_message(FATAL_ERROR "Conan: Component '${_FIND_COMPONENT}' NOT found in package '{{ pkg_name }}'")
                else()
                    conan_message(STATUS "Conan: Component '${_FIND_COMPONENT}' found in package '{{ pkg_name }}'")
                endif()
            endforeach()
        endif()
        """)

    def get_rename(self):
        ret = self.conanfile.new_cpp_info.get_property("cmake_target_name", "CMakeDeps")
        if not ret:
            ret = self.conanfile.cpp_info.get_name("cmake_find_package_multi", default_name=False)
        return ret or self.conanfile.ref.name
