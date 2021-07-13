import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooTargets.cmake

"""


class TargetsTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        return "{}Targets.cmake".format(self.file_name)

    @property
    def context(self):
        ret = {"pkg_name": self.pkg_name,
               "target_namespace": self.target_namespace,
               "file_name": self.file_name}
        return ret

    @property
    def template(self):
        return textwrap.dedent("""\
        # Load the debug and release variables
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB DATA_FILES "${_DIR}/{{ file_name }}-*-data.cmake")

        foreach(f ${DATA_FILES})
            include(${f})
        endforeach()

        # Create the targets for all the components
        foreach(_COMPONENT {{ '${' + pkg_name + '_COMPONENT_NAMES' + '}' }} )
            if(NOT TARGET {{ target_namespace }}::${_COMPONENT})
                add_library({{ target_namespace }}::${_COMPONENT} INTERFACE IMPORTED)
                conan_message(STATUS "Conan: Component target declared '{{ target_namespace }}::${_COMPONENT}'")
            endif()
        endforeach()

        if(NOT TARGET {{ target_namespace }}::{{ target_namespace }})
            add_library({{ target_namespace }}::{{ target_namespace }} INTERFACE IMPORTED)
            conan_message(STATUS "Conan: Target declared '{{ target_namespace }}::{{ target_namespace }}'")
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB CONFIG_FILES "${_DIR}/{{ file_name }}Target-*.cmake")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()
        """)
