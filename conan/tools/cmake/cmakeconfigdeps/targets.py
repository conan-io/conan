import textwrap

import jinja2
from jinja2 import Template


class TargetsTemplate2:
    """
    FooTargets.cmake
    """
    def __init__(self, cmakedeps, conanfile, cmake_file_name, cmake_file_info):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile
        self._cmake_file_name = cmake_file_name
        self._cmake_file_info = cmake_file_info

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        f = self._cmake_file_name
        return f"{f}Targets.cmake"

    @property
    def _context(self):
        ret = {"ref": (",".join(self._cmake_file_info["components"]) if not self._cmake_file_info["is_root"]
                       else str(self._conanfile.ref)),
               "filename": self._cmake_file_name}
        return ret

    @property
    def _template(self):
        return textwrap.dedent("""\
            include_guard()
            message(STATUS "Conan: Configuring Targets for {{ ref }}")

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
