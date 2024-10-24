import textwrap

import jinja2
from jinja2 import Template


class ConfigTemplate2:
    """
    FooConfig.cmake
    foo-config.cmake
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
        return f"{f}-config.cmake" if f == f.lower() else f"{f}Config.cmake"

    @property
    def _context(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        targets_include = f"{f}Targets.cmake"
        pkg_name = self._conanfile.ref.name
        build_modules_paths = self._cmakedeps.get_property("cmake_build_modules", self._conanfile,
                                                           check_type=list) or []
        # FIXME: Proper escaping of paths for CMake and relativization
        # FIXME: build_module_paths coming from last config only
        build_modules_paths = [f.replace("\\", "/") for f in build_modules_paths]
        return {"pkg_name": pkg_name,
                "targets_include_file": targets_include,
                "build_modules_paths": build_modules_paths}

    @property
    def _template(self):
        return textwrap.dedent("""\
        # Requires CMake > 3.15
        if(${CMAKE_VERSION} VERSION_LESS "3.15")
            message(FATAL_ERROR "The 'CMakeDeps' generator only works with CMake >= 3.15")
        endif()

        include(${CMAKE_CURRENT_LIST_DIR}/{{ targets_include_file }})

        get_property(isMultiConfig GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
        if(NOT isMultiConfig AND NOT CMAKE_BUILD_TYPE)
           message(FATAL_ERROR "Please, set the CMAKE_BUILD_TYPE variable when calling to CMake "
                               "adding the '-DCMAKE_BUILD_TYPE=<build_type>' argument.")
        endif()

        # build_modules_paths comes from last configuration only
        {% for build_module in build_modules_paths %}
        message(STATUS "Conan: Including build module from '{{build_module}}'")
        include("{{ build_module }}")
        {% endfor %}
        """)
