import os
import textwrap

import jinja2
from jinja2 import Template


class TargetConfigurationTemplate2:
    """
    FooTarget-release.cmake
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
        return f"{f}-Targets-{self._cmakedeps.configuration.lower()}.cmake"

    @property
    def _context(self):
        cpp_info = self._conanfile.cpp_info
        pkg_name = self._conanfile.ref.name
        config = self._cmakedeps.configuration.upper()
        package_folder = self._conanfile.package_folder.replace("\\", "/")
        package_folder_var = f"{pkg_name}_PACKAGE_FOLDER_{config}"

        exes = {}

        def _add_exe(info):
            if info.exe:
                target = info.get_property("cmake_target_name") or f"{pkg_name}::{info.exe}"
                exe_location = self._path(info.location, package_folder, package_folder_var)
                exes[target] = exe_location

        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                _add_exe(component)
        else:
            if cpp_info.exe:
                _add_exe(cpp_info)

        return {"package_folder": package_folder,
                "package_folder_var": package_folder_var,
                "config": config,
                "exes": exes}

    @staticmethod
    def _path(p, package_folder, package_folder_var):
        def escape(p_):
            return p_.replace("$", "\\$").replace('"', '\\"')

        p = p.replace("\\", "/")
        if os.path.isabs(p):
            if p.startswith(package_folder):
                rel = p[len(package_folder):]
                return f"${{{package_folder_var}}}/{escape(rel)}"
            return escape(p)

        return f"${{{package_folder_var}}}/{escape(p)}"

    @property
    def _template(self):
        return textwrap.dedent("""\
        set({{package_folder_var}} "{{package_folder}}")

        # Exe information
        {% for exe, location in exes.items() %}
        message(STATUS "Conan: Target declared imported executable '{{exe}}'")
        if(NOT TARGET {{ exe }})
            add_executable({{exe}} IMPORTED)
        endif()
        set_property(TARGET {{exe}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{exe}} PROPERTIES IMPORTED_LOCATION_{{config}} "{{location}}")

        {% endfor %}
        """)
