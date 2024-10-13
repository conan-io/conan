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
            for dependency in transitive_reqs.values():
                dep_pkg_name = dependency.ref.name
                result.append(f"{dep_pkg_name}::{dep_pkg_name}")
            return result

        for required_pkg, required_comp in requires:
            if required_pkg is None:  # Points to a component of same package
                dep_component = components[required_comp]
                dep_target = dep_component.get_property("cmake_target_name") or f"{pkg_name}::{required_comp}"
                result.append(dep_target)
            else:  # Different package
                try:  # Make sure the declared dependency is at least in the recipe requires
                    self._conanfile.dependencies[required_pkg]
                except KeyError:
                    raise ConanException(f"{self._conanfile}: component '{required_comp}' required "
                                         f"'{required_pkg}::{required_comp}', "
                                         f"but '{required_pkg}' is not a direct dependency")
                try:
                    req = transitive_reqs[required_pkg]
                except KeyError:  # The transitive dep might have been skipped
                    pass
                else:
                    # TODO: Missing cmake_target_name for req
                    dep_target = f"{required_pkg}::{required_comp}"
                    result.append(dep_target)
        return result

    @property
    def _context(self):
        cpp_info = self._conanfile.cpp_info.deduce_full_cpp_info(self._conanfile)
        pkg_name = self._conanfile.ref.name
        config = self._cmakedeps.configuration.upper()
        package_folder = self._conanfile.package_folder.replace("\\", "/")
        package_folder_var = f"{pkg_name}_PACKAGE_FOLDER_{config}"

        libs = {}

        def _add_libs(info, component_name=None):
            defines = " ".join(info.defines)
            includedirs = ";".join(self._path(i, package_folder, package_folder_var)
                                   for i in info.includedirs) if info.includedirs else ""
            requires = " ".join(self._requires(info, self._conanfile.cpp_info.components))
            cxxflags = " ".join(info.cxxflags)
            # TODO: Other cflags, linkflags
            if info.libs:  # TODO: Handle component_name for libs
                if len(info.libs) != 1:
                    raise ConanException(f"New CMakeDeps only allows 1 lib per component:\n"
                                         f"{self._conanfile}: {info.libs}")
                lib_name = info.libs[0]
                target_name = info.get_property("cmake_target_name") or f"{pkg_name}::{lib_name}"
                location = self._path(info.location, package_folder, package_folder_var)
                lib_type = "SHARED" if info.type is PackageType.SHARED else \
                    "STATIC" if info.type is PackageType.STATIC else \
                    "INTERFACE" if info.type is PackageType.HEADER else None

                if lib_type:
                    libs[target_name] = {"type": lib_type,
                                         "includedirs": includedirs,
                                         "location": location,
                                         "link_location": "",
                                         "requires": requires,
                                         "defines": defines,
                                         "cxxflags": cxxflags}
            elif info.includedirs and not info.exe:  # Pure header only
                cmp_name = component_name or pkg_name
                target_name = info.get_property("cmake_target_name") or f"{pkg_name}::{cmp_name}"
                libs[target_name] = {"type": "INTERFACE",
                                     "includedirs": includedirs,
                                     "defines": defines,
                                     "requires": requires,
                                     "cxxflags": cxxflags}

        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                _add_libs(component, name)
        else:
            _add_libs(cpp_info)

        if libs and f"{pkg_name}::{pkg_name}" not in libs:
            # Add a generic interface target for the package depending on the others
            if cpp_info.default_components is not None:
                all_requires = []
                for default_comp in cpp_info.default_components:
                    comp = cpp_info.components[default_comp]
                    comp_name = comp.get_property("cmake_target_name") or f"{pkg_name}::{default_comp}"
                    all_requires.append(comp_name)
                all_requires = " ".join(all_requires)
            else:
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

        # TODO: Missing find_modes
        dependencies = self._get_dependencies()
        return {"dependencies": dependencies,
                "package_folder": package_folder,
                "package_folder_var": package_folder_var,
                "config": config,
                "exes": exes,
                "libs": libs}

    def _get_dependencies(self):
        """ transitive dependencies Filenames for find_dependency()
        """
        # TODO: Filter build requires
        # if self._require.build:
        #    return []

        transitive_reqs = self._cmakedeps.get_transitive_requires(self._conanfile)
        ret = {self._cmakedeps.get_cmake_filename(r): None for r in transitive_reqs.values()}
        return ret

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

    @staticmethod
    def _escape_cmake_string(values):
        return " ".join(v.replace("\\", "\\\\").replace('$', '\\$').replace('"', '\\"')
                        for v in values)

    @property
    def _template(self):
        # TODO: Check why not set_property instead of target_link_libraries
        return textwrap.dedent("""\
        set({{package_folder_var}} "{{package_folder}}")

        # Dependencies finding
        include(CMakeFindDependencyMacro)

        {% for dep, dep_find_mode in dependencies.items() %}
        if(NOT {{dep}}_FOUND)
            find_dependency({{dep}} REQUIRED {{dep_find_mode}})
        endif()
        {% endfor %}

        ################# Libs information ##############
        {% for lib, lib_info in libs.items() %}
        #################### {{lib}} ####################
        message(STATUS "Conan: Target declared imported {{lib_info["type"]}} library '{{lib}}'")
        if(NOT TARGET {{ lib }})
            add_library({{lib}} {{lib_info["type"]}} IMPORTED)
        endif()
        {% if lib_info.get("includedirs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     $<$<CONFIG:{{config}}>:{{lib_info["includedirs"]}}>)
        {% endif %}
        {% if lib_info.get("defines") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     $<$<CONFIG:{{config}}>:{{lib_info["defines"]}}>)
        {% endif %}
        {% if lib_info.get("cxxflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<COMPILE_LANGUAGE:CXX>:$<$<CONFIG:{{config}}>:{{lib_info["cxxflags"]}}>>)
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

        ################# Exes information ##############
        {% for exe, location in exes.items() %}
        #################### {{exe}} ####################
        message(STATUS "Conan: Target declared imported executable '{{exe}}'")
        if(NOT TARGET {{ exe }})
            add_executable({{exe}} IMPORTED)
        endif()
        set_property(TARGET {{exe}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{exe}} PROPERTIES IMPORTED_LOCATION_{{config}} "{{location}}")

        {% endfor %}
        """)
