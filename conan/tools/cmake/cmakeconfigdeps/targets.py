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
        ret = {}
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        for config_comp_name, cmake_file_name in self._cmakedeps.get_cmake_filenames(self._conanfile).items():
            context = self._get_context(config_comp_name, cmake_file_name)
            filename = f"{cmake_file_name}Targets.cmake"
            ret[filename] = t.render(context)
        return ret

    def _get_context(self, comp_name, cmake_file_name):
        ret = {"ref": f"{str(self._conanfile.ref)} (Component: {comp_name})" if comp_name else str(self._conanfile.ref),
               "filename": cmake_file_name}
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
