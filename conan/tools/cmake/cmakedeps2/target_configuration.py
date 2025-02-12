import os
import textwrap

import jinja2
from jinja2 import Template

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conans.client.graph.graph import CONTEXT_BUILD, CONTEXT_HOST
from conan.internal.model.pkg_type import PackageType


class TargetConfigurationTemplate2:
    """
    FooTarget-release.cmake
    """
    def __init__(self, cmakedeps, conanfile, require):
        self._cmakedeps = cmakedeps
        self._conanfile = conanfile  # The dependency conanfile, not the consumer one
        self._require = require

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        # Fallback to consumer configuration if it doesn't have build_type
        config = self._conanfile.settings.get_safe("build_type", self._cmakedeps.configuration)
        config = (config or "none").lower()
        build = "Build" if self._conanfile.context == CONTEXT_BUILD else ""
        return f"{f}-Targets{build}-{config}.cmake"

    def _requires(self, info, components):
        result = []
        requires = info.parsed_requires()
        pkg_name = self._conanfile.ref.name
        transitive_reqs = self._cmakedeps.get_transitive_requires(self._conanfile)
        if not requires and not components:  # global cpp_info without components definition
            # require the pkgname::pkgname base (user defined) or INTERFACE base target
            targets = []
            for d in transitive_reqs.values():
                dep_target = self._cmakedeps.get_property("cmake_target_name", d)
                targets.append(dep_target or f"{d.ref.name}::{d.ref.name}")
            return targets

        for required_pkg, required_comp in requires:
            if required_pkg is None:  # Points to a component of same package
                dep_comp = components.get(required_comp)
                assert dep_comp, f"Component {required_comp} not found in {self._conanfile}"
                dep_target = self._cmakedeps.get_property("cmake_target_name", self._conanfile,
                                                          required_comp)
                dep_target = dep_target or f"{pkg_name}::{required_comp}"
                result.append(dep_target)
            else:  # Different package
                try:
                    dep = transitive_reqs[required_pkg]
                except KeyError:  # The transitive dep might have been skipped
                    pass
                else:
                    # To check if the component exist, it is ok to use the standard cpp_info
                    # No need to use the cpp_info = deduce_cpp_info(dep)
                    dep_comp = dep.cpp_info.components.get(required_comp)
                    if dep_comp is None:
                        # It must be the interface pkgname::pkgname target
                        assert required_pkg == required_comp
                        comp = None
                        default_target = f"{dep.ref.name}::{dep.ref.name}"  # replace_requires
                    else:
                        comp = required_comp
                        default_target = f"{required_pkg}::{required_comp}"
                    dep_target = self._cmakedeps.get_property("cmake_target_name", dep, comp)
                    dep_target = dep_target or default_target
                    result.append(dep_target)
        return result

    @property
    def _context(self):
        cpp_info = self._conanfile.cpp_info.deduce_full_cpp_info(self._conanfile)
        pkg_name = self._conanfile.ref.name
        # fallback to consumer configuration if it doesn't have build_type
        config = self._conanfile.settings.get_safe("build_type", self._cmakedeps.configuration)
        config = config.upper() if config else None
        pkg_folder = self._conanfile.package_folder.replace("\\", "/")
        config_folder = f"_{config}" if config else ""
        build = "_BUILD" if self._conanfile.context == CONTEXT_BUILD else ""
        pkg_folder_var = f"{pkg_name}_PACKAGE_FOLDER{config_folder}{build}"

        libs = {}
        # The BUILD context does not generate libraries targets atm
        if self._conanfile.context == CONTEXT_HOST:
            libs = self._get_libs(cpp_info, pkg_name, pkg_folder, pkg_folder_var)
            self._add_root_lib_target(libs, pkg_name, cpp_info)
        exes = self._get_exes(cpp_info, pkg_name, pkg_folder, pkg_folder_var)

        prefixes = self._cmakedeps.get_property("cmake_additional_variables_prefixes",
                                                self._conanfile, check_type=list) or []
        f = self._cmakedeps.get_cmake_filename(self._conanfile)
        prefixes = [f] + prefixes
        include_dirs = definitions = libraries = None
        if not self._require.build:  # To add global variables for try_compile and legacy
            aggregated_cppinfo = cpp_info.aggregated_components()
            # FIXME: Proper escaping of paths for CMake and relativization
            include_dirs = ";".join(i.replace("\\", "/") for i in aggregated_cppinfo.includedirs)
            definitions = ""
            root_target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile)
            libraries = root_target_name or f"{pkg_name}::{pkg_name}"

        # TODO: Missing find_modes
        dependencies = self._get_dependencies()
        return {"dependencies": dependencies,
                "pkg_folder": pkg_folder,
                "pkg_folder_var": pkg_folder_var,
                "config": config,
                "exes": exes,
                "libs": libs,
                "context": self._conanfile.context,
                # Extra global variables
                "additional_variables_prefixes": prefixes,
                "version": self._conanfile.ref.version,
                "include_dirs": include_dirs,
                "definitions": definitions,
                "libraries": libraries
                }

    def _get_libs(self, cpp_info, pkg_name, pkg_folder, pkg_folder_var) -> dict:
        libs = {}
        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile,
                                                           name)
                target_name = target_name or f"{pkg_name}::{name}"
                target = self._get_cmake_lib(component, cpp_info.components, pkg_folder,
                                             pkg_folder_var)
                if target is not None:
                    libs[target_name] = target
        else:
            target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile)
            target_name = target_name or f"{pkg_name}::{pkg_name}"
            target = self._get_cmake_lib(cpp_info, None, pkg_folder, pkg_folder_var)
            if target is not None:
                libs[target_name] = target
        return libs

    def _get_cmake_lib(self, info, components, pkg_folder, pkg_folder_var):
        if info.exe or not (info.includedirs or info.libs):
            return

        includedirs = ";".join(self._path(i, pkg_folder, pkg_folder_var)
                               for i in info.includedirs) if info.includedirs else ""
        requires = ";".join(self._requires(info, components))
        defines = " ".join(info.defines)
        # TODO: Missing escaping?
        # TODO: Missing link language
        # FIXME: Filter by lib traits!!!!!
        if not self._require.headers:  # If not depending on headers, paths and
            includedirs = defines = None
        system_libs = " ".join(info.system_libs)
        target = {"type": "INTERFACE",
                  "includedirs": includedirs,
                  "defines": defines,
                  "requires": requires,
                  "cxxflags": " ".join(info.cxxflags),
                  "cflags": " ".join(info.cflags),
                  "sharedlinkflags": " ".join(info.sharedlinkflags),
                  "exelinkflags": " ".join(info.exelinkflags),
                  "system_libs": system_libs}

        if info.frameworks:
            ConanOutput(scope=str(self._conanfile)).warning("frameworks not supported yet in new CMakeDeps generator")

        if info.libs:
            if len(info.libs) != 1:
                raise ConanException(f"New CMakeDeps only allows 1 lib per component:\n"
                                     f"{self._conanfile}: {info.libs}")
            assert info.location, "info.location missing for .libs, it should have been deduced"
            location = self._path(info.location, pkg_folder, pkg_folder_var)
            link_location = self._path(info.link_location, pkg_folder, pkg_folder_var) \
                if info.link_location else None
            lib_type = "SHARED" if info.type is PackageType.SHARED else \
                "STATIC" if info.type is PackageType.STATIC else None
            assert lib_type, f"Unknown package type {info.type}"
            target["type"] = lib_type
            target["location"] = location
            target["link_location"] = link_location
            link_languages = info.languages or self._conanfile.languages or []
            link_languages = ["CXX" if c == "C++" else c for c in link_languages]
            target["link_languages"] = link_languages

        return target

    def _add_root_lib_target(self, libs, pkg_name, cpp_info):
        """
        Addd a new pkgname::pkgname INTERFACE target that depends on default_components or
        on all other library targets (not exes)
        It will not be added if there exists already a pkgname::pkgname target.
        """
        root_target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile)
        root_target_name = root_target_name or f"{pkg_name}::{pkg_name}"
        # TODO: What if an exe target is called like the pkg_name::pkg_name
        if libs and root_target_name not in libs:
            # Add a generic interface target for the package depending on the others
            if cpp_info.default_components is not None:
                all_requires = []
                for defaultc in cpp_info.default_components:
                    target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile,
                                                               defaultc)
                    comp_name = target_name or f"{pkg_name}::{defaultc}"
                    all_requires.append(comp_name)
                all_requires = ";".join(all_requires)
            else:
                all_requires = ";".join(libs.keys())
            libs[root_target_name] = {"type": "INTERFACE",
                                      "requires": all_requires}

    def _get_exes(self, cpp_info, pkg_name, pkg_folder, pkg_folder_var):
        exes = {}

        if cpp_info.has_components:
            for name, comp in cpp_info.components.items():
                if comp.exe or comp.type is PackageType.APP:
                    target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile,
                                                               name)
                    target = target_name or f"{pkg_name}::{name}"
                    exe_location = self._path(comp.location, pkg_folder, pkg_folder_var)
                    exes[target] = exe_location
        else:
            if cpp_info.exe:
                target_name = self._cmakedeps.get_property("cmake_target_name", self._conanfile)
                target = target_name or f"{pkg_name}::{pkg_name}"
                exe_location = self._path(cpp_info.location, pkg_folder, pkg_folder_var)
                exes[target] = exe_location

        return exes

    def _get_dependencies(self):
        """ transitive dependencies Filenames for find_dependency()
        """
        # Build requires are already filtered by the get_transitive_requires
        transitive_reqs = self._cmakedeps.get_transitive_requires(self._conanfile)
        # FIXME: Hardcoded CONFIG
        ret = {self._cmakedeps.get_cmake_filename(r): "CONFIG" for r in transitive_reqs.values()}
        return ret

    @staticmethod
    def _path(p, pkg_folder, pkg_folder_var):
        def escape(p_):
            return p_.replace("$", "\\$").replace('"', '\\"')

        p = p.replace("\\", "/")
        if os.path.isabs(p):
            if p.startswith(pkg_folder):
                rel = p[len(pkg_folder):].lstrip("/")
                return f"${{{pkg_folder_var}}}/{escape(rel)}"
            return escape(p)
        return f"${{{pkg_folder_var}}}/{escape(p)}"

    @staticmethod
    def _escape_cmake_string(values):
        return " ".join(v.replace("\\", "\\\\").replace('$', '\\$').replace('"', '\\"')
                        for v in values)

    @property
    def _template(self):
        # TODO: Check why not set_property instead of target_link_libraries
        return textwrap.dedent("""\
        {%- macro config_wrapper(config, value) -%}
             {% if config -%}
             $<$<CONFIG:{{config}}>:{{value}}>
             {%- else -%}
             {{value}}
             {%- endif %}
        {%- endmacro -%}
        set({{pkg_folder_var}} "{{pkg_folder}}")

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
        if(NOT TARGET {{ lib }})
            message(STATUS "Conan: Target declared imported {{lib_info["type"]}} library '{{lib}}'")
            add_library({{lib}} {{lib_info["type"]}} IMPORTED)
        endif()
        {% if lib_info.get("includedirs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     {{config_wrapper(config, lib_info["includedirs"])}})
        {% endif %}
        {% if lib_info.get("defines") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     {{config_wrapper(config, lib_info["defines"])}})
        {% endif %}
        {% if lib_info.get("cxxflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<COMPILE_LANGUAGE:CXX>:{{config_wrapper(config, lib_info["cxxflags"])}}>)
        {% endif %}
        {% if lib_info.get("cflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     $<$<COMPILE_LANGUAGE:C>:{{config_wrapper(config, lib_info["cflags"])}}>)
        {% endif %}
        {% if lib_info.get("sharedlinkflags") %}
        {% set linkflags = config_wrapper(config, lib_info["sharedlinkflags"]) %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_OPTIONS
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{linkflags}}>"
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{linkflags}}>")
        {% endif %}
        {% if lib_info.get("exelinkflags") %}
        {% set exeflags = config_wrapper(config, lib_info["exelinkflags"]) %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_OPTIONS
                     "$<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{exeflags}}>")
        {% endif %}

        {% if lib_info.get("link_languages") %}
        get_property(_languages GLOBAL PROPERTY ENABLED_LANGUAGES)
        {% for lang in lib_info["link_languages"] %}
        if(NOT "{{lang}}" IN_LIST _languages)
            message(SEND_ERROR
                    "Target {{lib}} has {{lang}} linkage but {{lang}} not enabled in project()")
        endif()
        set_property(TARGET {{lib}} APPEND PROPERTY
                     IMPORTED_LINK_INTERFACE_LANGUAGES_{{config}} {{lang}})
        {% endfor %}
        {% endif %}
        {% if lib_info.get("location") %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{lib}} PROPERTIES IMPORTED_LOCATION_{{config}}
                              "{{lib_info["location"]}}")
        {% endif %}
        {% if lib_info.get("link_location") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_IMPLIB_{{config}}
                              "{{lib_info["link_location"]}}")
        {% endif %}
        {% if lib_info.get("requires") %}
        set_target_properties({{lib}} PROPERTIES INTERFACE_LINK_LIBRARIES
                              "{{config_wrapper(config, lib_info["requires"])}}")
        {% endif %}
        {% if lib_info.get("system_libs") %}
        target_link_libraries({{lib}} INTERFACE {{lib_info["system_libs"]}})
        {% endif %}

        {% endfor %}

        ################# Global variables for try compile and legacy ##############
        {% for prefix in additional_variables_prefixes %}
        set({{ prefix }}_VERSION_STRING "{{ version }}")
        {% if include_dirs is not none %}
        set({{ prefix }}_INCLUDE_DIRS "{{ include_dirs }}" )
        set({{ prefix }}_INCLUDE_DIR "{{ include_dirs }}" )
        {% endif %}
        {% if libraries is not none %}
        set({{ prefix }}_LIBRARIES {{ libraries }} )
        {% endif %}
        {% if definitions is not none %}
        set({{ prefix }}_DEFINITIONS {{ definitions}} )
        {% endif %}
        {% endfor %}

        ################# Exes information ##############
        {% for exe, location in exes.items() %}
        #################### {{exe}} ####################
        if(NOT TARGET {{ exe }})
            message(STATUS "Conan: Target declared imported executable '{{exe}}' {{context}}")
            add_executable({{exe}} IMPORTED)
        else()
            get_property(_context TARGET {{exe}} PROPERTY CONAN_CONTEXT)
            if(NOT $${_context} STREQUAL "{{context}}")
                message(STATUS "Conan: Exe {{exe}} was already defined in ${_context}")
                get_property(_configurations TARGET {{exe}} PROPERTY IMPORTED_CONFIGURATIONS)
                message(STATUS "Conan: Exe {{exe}} defined configurations: ${_configurations}")
                foreach(_config ${_configurations})
                    set_property(TARGET {{exe}} PROPERTY IMPORTED_LOCATION_${_config})
                endforeach()
                set_property(TARGET {{exe}} PROPERTY IMPORTED_CONFIGURATIONS)
            endif()
        endif()
        set_property(TARGET {{exe}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{exe}} PROPERTIES IMPORTED_LOCATION_{{config}} "{{location}}")
        set_property(TARGET {{exe}} PROPERTY CONAN_CONTEXT "{{context}}")
        {% endfor %}
        """)
