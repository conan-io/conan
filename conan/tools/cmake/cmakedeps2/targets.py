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
        data_pattern = "${CMAKE_CURRENT_LIST_DIR}/" if not self.generating_module else "${CMAKE_CURRENT_LIST_DIR}/module-"
        data_pattern += "{}-*-data.cmake".format(self.file_name)

        target_pattern = "" if not self.generating_module else "module-"
        target_pattern += "{}-Target-*.cmake".format(self.file_name)

        cmake_target_aliases = self.conanfile.cpp_info.\
            get_property("cmake_target_aliases", check_type=list) or dict()

        target = self.root_target_name
        cmake_target_aliases = {alias: target for alias in cmake_target_aliases}

        cmake_component_target_aliases = dict()
        for comp_name in self.conanfile.cpp_info.components:
            if comp_name is not None:
                aliases = \
                    self.conanfile.cpp_info.components[comp_name].\
                    get_property("cmake_target_aliases", check_type=list) or dict()

                target = self.get_component_alias(self.conanfile, comp_name)
                cmake_component_target_aliases[comp_name] = {alias: target for alias in aliases}

        ret = {"pkg_name": self.pkg_name,
               "root_target_name": self.root_target_name,
               "file_name": self.file_name,
               "data_pattern": data_pattern,
               "target_pattern": target_pattern,
               "cmake_target_aliases": cmake_target_aliases,
               "cmake_component_target_aliases": cmake_component_target_aliases}

        return ret

    @property
    def _template(self):
        return textwrap.dedent("""\
        # Load the debug and release variables
        file(GLOB DATA_FILES "{{data_pattern}}")

        foreach(f ${DATA_FILES})
            include(${f})
        endforeach()


        # Load the debug and release library finders
        file(GLOB CONFIG_FILES "${CMAKE_CURRENT_LIST_DIR}/{{ target_pattern }}")

        foreach(f ${CONFIG_FILES})
            include(${f})
        endforeach()
        """)
