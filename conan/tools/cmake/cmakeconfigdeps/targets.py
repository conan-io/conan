import textwrap

import jinja2

from conan.internal.util.templates import compiled_template


class TargetsTemplate2:
    """
    FooTargets.cmake

    Thin Jinja renderer. Filename and context are built by CMakeConfigDeps.
    """
    def __init__(self, filename, context):
        self._filename = filename
        self._context = context

    @property
    def filename(self):
        return self._filename

    def content(self):
        t = compiled_template(self._template, undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    _template = textwrap.dedent("""\
            include_guard()
            if(NOT ${CMAKE_FIND_PACKAGE_NAME}_FIND_QUIETLY)
                message(STATUS "Conan: Configuring Targets for {{ filename }}")
            endif()

            # Load information for each installed configuration.
            file(GLOB _target_files "${CMAKE_CURRENT_LIST_DIR}/{{filename}}-Targets-*.cmake")
            foreach(_target_file IN LISTS _target_files)
              include("${_target_file}")
            endforeach()

            file(GLOB _build_files "${CMAKE_CURRENT_LIST_DIR}/{{filename}}-TargetsBuild-*.cmake")
            foreach(_build_file IN LISTS _build_files)
              include("${_build_file}")
            endforeach()
            """)
