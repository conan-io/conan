import os
import textwrap

import jinja2
from jinja2 import Template

from conan.errors import ConanException
from conans.model.pkg_type import PackageType


class TargetConfigurationTemplate2:
    """
    FooTarget-release.cmake
    """
    def __init__(self, cmakedeps, conanfile):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile  # The dependency conanfile, not the consumer one

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        print(t.render(self._context))
        return t.render(self._context)

    @property
    def filename(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        return f"{f}-Targets-{self._cmakedeps.configuration.lower()}.cmake"

    def _requires(self, info, components):
        result = []
        requires = info.parsed_requires()
        pkg_name = self._conanfile.ref.name
        transitive_reqs = self._cmakedeps.get_transitive_requires(self._conanfile)
        if not requires and not components:  # global cpp_info without components definition
            # TODO: Not tested at all
            for dependency in transitive_reqs.values():
                dep_pkg_name = dependency.ref.name
                dep_cpp_info = dependency.cpp_info
                if dep_cpp_info.has_components:
                    for name, component in dep_cpp_info.components.items():
                        result.append(f"{dep_pkg_name}::{name}")
                else:
                    result.append("{dep_pkg_name}::{dep_pkg_name}")
            return result

        for required_scope, required_comp in requires:
            if required_scope is None:  # Points to a component of same package
                dep_component = components[required_comp]
                dep_target = dep_component.get_property("cmake_target_name") or f"{pkg_name}::{required_comp}"
                result.append(dep_target)
            else:  # Different package
                try:  # Make sure the declared dependency is at least in the recipe requires
                    self._conanfile.dependencies[required_pkg]
                except KeyError:
                    raise ConanException(f"{self.conanfile}: component '{comp_name}' required "
                                         f"'{required_pkg}::{required_comp}', "
                                         f"but '{required_pkg}' is not a direct dependency")
                try:
                    req = transitive_requires[required_pkg]
                except KeyError:  # The transitive dep might have been skipped
                    pass
                else:
                    public_comp_deps.append(self.get_component_alias(req, required_comp))
        return result

    @property
    def _context(self):
        cpp_info = self._conanfile.cpp_info
        pkg_name = self._conanfile.ref.name
        config = self._cmakedeps.configuration.upper()
        package_folder = self._conanfile.package_folder.replace("\\", "/")
        package_folder_var = f"{pkg_name}_PACKAGE_FOLDER_{config}"

        libs = {}

        def _add_libs(info):
            if info.libs:
                assert len(info.libs) == 1, "New CMakeDeps only allows 1 lib per component"
                lib_name = info.libs[0]
                target_name = info.get_property("cmake_target_name") or f"{pkg_name}::{lib_name}"
                info.deduce_cps(self._conanfile.package_type)
                location = self._path(info.location, package_folder, package_folder_var)
                lib_type = "SHARED" if info.type is PackageType.SHARED else \
                    "STATIC" if info.type is PackageType.STATIC else \
                    "INTERFACE" if info.type is PackageType.HEADER else None
                includedirs = ";".join(self._path(i, package_folder, package_folder_var)
                                       for i in info.includedirs) if info.includedirs else ""
                requires = " ".join(self._requires(info, self._conanfile.cpp_info.components))
                if lib_type:
                    libs[target_name] = {"type": lib_type,
                                         "includedirs": includedirs,
                                         "location": location,
                                         "link_location": "",
                                         "requires": requires}

        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                _add_libs(component)
        else:
            _add_libs(cpp_info)

        if libs and f"{pkg_name}::{pkg_name}" not in libs:
            # Add a generic interface target for the package depending on the others
            all_requires = " ".join(libs.keys())
            libs[f"{pkg_name}::{pkg_name}"] = {"type": "INTERFACE",
                                               "requires": all_requires}

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
                "exes": exes,
                "libs": libs}

    @staticmethod
    def _path(p, package_folder, package_folder_var):
        def escape(p_):
            return p_.replace("$", "\\$").replace('"', '\\"')

        p = p.replace("\\", "/")
        if os.path.isabs(p):
            if p.startswith(package_folder):
                rel = p[len(package_folder):].lstrip("/")
                return f"${{{package_folder_var}}}/{escape(rel)}"
            return escape(p)
        return f"${{{package_folder_var}}}/{escape(p)}"

    @property
    def _template(self):
        # TODO: Check why not set_property instead of target_link_libraries
        return textwrap.dedent("""\
        set({{package_folder_var}} "{{package_folder}}")

        # Libs information
        {% for lib, lib_info in libs.items() %}
        message(STATUS "Conan: Target declared imported {{lib_info["type"]}} library '{{lib}}'")
        if(NOT TARGET {{ lib }})
            add_library({{lib}} {{lib_info["type"]}} IMPORTED)
        endif()
        {% if lib_info.get("includedirs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{config}}>:{{lib_info["includedirs"]}}>)
        {% endif %}
        {% if lib_info["type"] != "INTERFACE" %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{lib}} PROPERTIES IMPORTED_LOCATION_{{config}}
                              "{{lib_info["location"]}}")
        {% endif %}
        {% if lib_info.get("link_location") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_IMPLIB_{{config}}
                              "{{lib_info["link_location"]}}")
        {% endif %}
        {% if lib_info.get("requires") %}
        target_link_libraries({{lib}} INTERFACE {{lib_info["requires"]}})
        {% endif %}

        {% endfor %}

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
