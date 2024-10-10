import textwrap

import jinja2
from jinja2 import Template


class TargetsTemplate2:
    """
    FooTargets.cmake
    """
    def __init__(self, cmakedeps, conanfile):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        return f"{f}Targets.cmake"

    @property
    def _context(self):
        filename = self._cmakedeps.get_cmake_filename(self._conanfile)
        ret = {"ref": str(self._conanfile.ref),
               "filename": filename}
        return ret

    @property
    def _template(self):
        # TODO: What if target exists only in Debug or Release?
        return textwrap.dedent("""\
            message(STATUS "Configuring Targets for {{ ref }}")

            # Load information for each installed configuration.
            file(GLOB _cmake_config_files "${CMAKE_CURRENT_LIST_DIR}/{{filename}}-Targets-*.cmake")
            foreach(_cmake_config_file IN LISTS _cmake_config_files)
              include("${_cmake_config_file}")
            endforeach()
        """)
