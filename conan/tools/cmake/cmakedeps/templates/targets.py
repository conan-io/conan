import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate

"""

FooTargets.cmake

"""


class TargetsTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        name = "" if not self.find_module_mode else "module-"
        name += self.file_name + "Targets.cmake"
        return name

    @property
    def context(self):
        data_pattern = "${_DIR}/" if not self.find_module_mode else "${_DIR}/module-"
        data_pattern += "{}-*-data.cmake".format(self.file_name)

        target_pattern = "" if not self.find_module_mode else "module-"
        target_pattern += "{}-Target-*.cmake".format(self.file_name)

        ret = {"pkg_name": self.pkg_name,
               "target_namespace": self.target_namespace,
               "global_target_name": self.global_target_name,
               "file_name": self.file_name,
               "data_pattern": data_pattern,
               "target_pattern": target_pattern}

        return ret

    @property
    def template(self):
        return textwrap.dedent("""\
        # Load the debug and release variables
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB DATA_FILES "{{data_pattern}}")

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

        if(NOT TARGET {{ target_namespace }}::{{ global_target_name }})
            add_library({{ target_namespace }}::{{ global_target_name }} INTERFACE IMPORTED)
            conan_message(STATUS "Conan: Target declared '{{ target_namespace }}::{{ global_target_name }}'")
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${CMAKE_CURRENT_LIST_FILE}" PATH)
        file(GLOB CONFIG_FILES "${_DIR}/{{ target_pattern }}")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()
        """)
