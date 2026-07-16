import os
import textwrap

import jinja2
from jinja2 import Template

from conan.errors import ConanException
from conan.internal.api.install.generators import relativize_path
from conan.internal.model.pkg_type import PackageType
from conan.tools.cmake.utils import cmake_escape_value


class TargetConfigurationTemplate2:
    """
    FooTarget-release.cmake
    """
    def __init__(self, filename, conanfile, consumer_conanfile, full_cpp_info,
                 is_build_context, require_headers, cmake_properties, transitive_reqs):
        self._filename = filename
        self._conanfile = conanfile  # The dependency conanfile, not the consumer one
        self._consumer_conanfile = consumer_conanfile
        self._full_cpp_info = full_cpp_info
        self._is_build_context = is_build_context
        self._require_headers = require_headers
        self._cmake_properties = cmake_properties
        self._transitive_reqs = transitive_reqs

        build_type = self._get_build_type()
        self._config = build_type.upper() if build_type else None
        config_folder = f"_{self._config}" if self._config else ""
        build_suffix = "_BUILD" if self._is_build_context else ""
        self._pkg_folder = conanfile.package_folder.replace("\\", "/")
        self._pkg_folder_var = (f"{conanfile.ref.name}_PACKAGE_FOLDER"
                                f"{config_folder}{build_suffix}")

    def content(self):
        t = Template(self._template, trim_blocks=True, lstrip_blocks=True,
                     undefined=jinja2.StrictUndefined)
        return t.render(self._context)

    @property
    def filename(self):
        config = (self._get_build_type() or "none").lower()
        build = "Build" if self._is_build_context else ""
        return f"{self._filename}-Targets{build}-{config}.cmake"

    def _get_build_type(self):
        return self._conanfile.settings.get_safe(
            "build_type", str(self._consumer_conanfile.settings.build_type))

    def _cmake_prop(self, dep_name, prop, comp_name=None):
        return self._cmake_properties[(dep_name, comp_name)][prop]

    def _get_cmake_target_name(self, pkg_name=None, comp_name=None):
        pkg_name = pkg_name or self._conanfile.ref.name
        target_name = self._cmake_prop(pkg_name, "cmake_target_name", comp_name)
        default = f"{pkg_name}::{comp_name}" if comp_name else f"{pkg_name}::{pkg_name}"
        return target_name or default

    def _get_dependencies_and_requires(self):
        dependencies = {self._cmake_prop(dep.ref.name, "cmake_file_name"): "CONFIG"
                        for dep in self._transitive_reqs.values()}
        extra_mods = self._cmake_prop(self._conanfile.ref.name, "cmake_extra_dependencies")
        dependencies.update({extra_mod: "" for extra_mod in extra_mods})

        requires = {}
        cpp_info = self._full_cpp_info
        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                requires[name] = self._get_component_requires(component, cpp_info.components)
        else:
            requires[None] = self._get_component_requires(cpp_info, None)
        return dependencies, requires

    def _get_component_requires(self, info, components):
        result = {}
        requires = info.parsed_requires()
        pkg_name = self._conanfile.ref.name
        pkg_type = info.type
        assert isinstance(pkg_type, PackageType), f"Pkg type {pkg_type} {type(pkg_type)}"
        transitive_reqs = self._transitive_reqs

        if not requires and not components:  # global cpp_info without components definition
            # require the pkgname::pkgname base (user defined) or INTERFACE base target
            for req, d in transitive_reqs.items():
                if d.package_type is PackageType.APP:
                    continue
                dep_target = self._get_cmake_target_name(d.ref.name)
                link_feature = self._cmake_prop(d.ref.name, "cmake_link_feature")
                result[dep_target] = {
                    "link": req.libs,
                    "link_feature": link_feature
                }
            return result

        for required_pkg, required_comp in requires:
            if required_pkg is None:  # Points to a component of same package
                dep_comp = components.get(required_comp)
                assert dep_comp, f"Component {required_comp} not found in {self._conanfile}"
                dep_target = self._get_cmake_target_name(comp_name=required_comp)
                link_feature = self._cmake_prop(pkg_name, "cmake_link_feature", required_comp)
                result[dep_target] = {
                    "link": True,  # Components of same package have PUBLIC dependency
                    "link_feature": link_feature
                }
            else:  # Different package
                try:
                    req, dep = transitive_reqs.of(required_pkg)
                except KeyError:  # The transitive dep might have been skipped
                    pass
                else:
                    # To check if the component exist, it is ok to use the standard cpp_info
                    # No need to use the cpp_info = deduce_cpp_info(dep)
                    dep_comp = dep.cpp_info.components.get(required_comp)
                    if dep_comp is None:
                        # It must be the interface pkgname::pkgname target
                        if required_pkg != required_comp:
                            msg = (f"{self._conanfile} recipe cpp_info did .requires to "
                                   f"'{required_pkg}::{required_comp}' but component "
                                   f"'{required_comp}' not found in {required_pkg}")
                            raise ConanException(msg)
                        if dep.package_type is PackageType.APP:
                            continue  # It doesn't make sense to link a package that is an App
                        comp = None
                        default_target = f"{dep.ref.name}::{dep.ref.name}"  # replace_requires
                        link = req.libs  # Do what the requirement to that package says
                    else:
                        if dep_comp.type is PackageType.APP or dep_comp.exe:
                            continue  # It doesn't make sense to link a package that is an App
                        comp = required_comp
                        default_target = f"{required_pkg}::{required_comp}"
                        # if it contains a requirement of a specific component of the other package
                        # and the other package can be an APP, but containing a LIB component
                        # the req.libs will not be defined. This is the libtool->automake(app) case
                        link = not (pkg_type is PackageType.SHARED and
                                    dep_comp.type is PackageType.SHARED)
                    link = req.libs or link
                    dep_target = self._cmake_prop(dep.ref.name, "cmake_target_name", comp)
                    dep_target = dep_target or default_target
                    link_feature = self._cmake_prop(dep.ref.name, "cmake_link_feature", comp)

                    result[dep_target] = {
                        "link": link,
                        "link_feature": link_feature
                    }
        return result

    @property
    def _context(self):
        cpp_info = self._full_cpp_info
        assert isinstance(cpp_info.type, PackageType)

        dependencies, cpp_info_requires = self._get_dependencies_and_requires()

        libs = {}
        # The BUILD context does not generate libraries targets atm
        if not self._is_build_context:
            libs = self._get_libs(cpp_info, cpp_info_requires)
            self._add_root_lib_target(libs, cpp_info)

        exes = self._get_exes(cpp_info)

        seen_aliases = set()
        root_target_name = self._get_cmake_target_name()
        for lib in libs.values():
            for alias in lib.get("cmake_target_aliases", []):
                if alias == root_target_name:
                    raise ConanException(f"Can't define an alias '{alias}' for the "
                                         f"root target '{root_target_name}' in {self._conanfile}. "
                                         f"Changing the default target should be done with the "
                                         f"'cmake_target_name' property.")
                if alias in seen_aliases:
                    raise ConanException(f"Alias '{alias}' already defined in {self._conanfile}. ")
                seen_aliases.add(alias)
                if alias in libs:
                    raise ConanException(f"Alias '{alias}' already defined as a target in "
                                         f"{self._conanfile}. ")

        pkg_folder = relativize_path(self._pkg_folder, self._consumer_conanfile,
                                     "${CMAKE_CURRENT_LIST_DIR}")
        return {"dependencies": dependencies,
                "pkg_folder": pkg_folder,
                "pkg_folder_var": self._pkg_folder_var,
                "config": self._config,
                "exes": exes,
                "libs": libs,
                "context": self._conanfile.context
                }

    def _get_libs(self, cpp_info, cpp_info_requires) -> dict:
        libs = {}
        if cpp_info.has_components:
            for name, component in cpp_info.components.items():
                target_name = self._get_cmake_target_name(comp_name=name)
                target = self._get_cmake_lib(component, cpp_info_requires, comp_name=name)
                if target is not None:
                    cmake_target_aliases = self._get_aliases(name)
                    target["cmake_target_aliases"] = cmake_target_aliases
                    libs[target_name] = target
        else:
            target_name = self._get_cmake_target_name()
            target = self._get_cmake_lib(cpp_info, cpp_info_requires)
            if target is not None:
                cmake_target_aliases = self._get_aliases()
                target["cmake_target_aliases"] = cmake_target_aliases
                libs[target_name] = target
        return libs

    def _get_cmake_lib(self, info, cpp_info_requires, comp_name=None):
        if info.exe or not (info.package_framework or info.frameworks or info.includedirs or info.libs
                            or info.system_libs or info.defines or info.requires):
            return

        includedirs = ";".join(self._path(i)
                               for i in info.includedirs) if info.includedirs else ""
        requires = cpp_info_requires[comp_name]
        assert isinstance(requires, dict)
        defines = ";".join(cmake_escape_value(f) for f in info.defines)
        # FIXME: Filter by lib traits!!!!!
        if not self._require_headers:  # If not depending on headers, paths and
            includedirs = defines = None
        extra_libs = self._cmake_prop(self._conanfile.ref.name, "cmake_extra_interface_libs",
                                      comp_name)
        sources = [self._path(source) for source in info.sources]
        target = {"type": "INTERFACE",
                  "comp_name": comp_name,
                  "includedirs": includedirs,
                  "defines": defines,
                  "requires": requires,
                  "cxxflags": ";".join(cmake_escape_value(f) for f in info.cxxflags),
                  "cflags": ";".join(cmake_escape_value(f) for f in info.cflags),
                  "sharedlinkflags": ";".join(cmake_escape_value(v) for v in info.sharedlinkflags),
                  "exelinkflags": ";".join(cmake_escape_value(v) for v in info.exelinkflags),
                  "system_libs": " ".join(info.system_libs + extra_libs),
                  "sources": " ".join(sources)
                  }
        # System frameworks (only Apple OS)
        if info.frameworks:
            target['frameworks'] = " ".join([f"-framework {frw}" for frw in info.frameworks])
        # FIXME: We're ignoring this value at this moment. It relies on cmake_target_name or lib name
        #        Revisit when cpp.exe value is used too.
        if info.package_framework:
            assert isinstance(info.package_framework, str), f"package_framework should be a str"
            if info.libs:
                raise ConanException("Can't define .libs and .package_framework for the same component")
            target["package_framework"] = {}
            lib_type = "SHARED" if info.type is PackageType.SHARED else \
                "STATIC" if info.type is PackageType.STATIC else "STATIC"
            assert lib_type, f"Unknown package type {info.type}"
            assert info.location, f"cpp_info.location missing for framework {info.package_framework}"
            target["type"] = lib_type
            target["package_framework"]["location"] = self._path(info.location)
            target["includedirs"] = []  # empty as frameworks have their own way to inject headers
            # FIXME: This is not needed for CMake < 3.24. Remove it when Conan requires CMake >= 3.24
            target["package_framework"]["frameworkdir"] = self._path(self._pkg_folder)
        if info.libs:
            if len(info.libs) != 1:
                raise ConanException(f"New CMakeDeps only allows 1 lib per component:\n"
                                     f"{self._conanfile}: {info.libs}")
            assert info.location, "info.location missing for .libs, it should have been deduced"
            location = self._path(info.location)
            link_location = self._path(info.link_location) \
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
            if lib_type == "SHARED" and self._cmake_prop(self._conanfile.ref.name, "nosoname",
                                                         comp_name):
                target["no_soname"] = True
        return target

    def _get_aliases(self, comp_name=None):
        return self._cmake_prop(self._conanfile.ref.name, "cmake_target_aliases", comp_name)

    def _add_root_lib_target(self, libs, cpp_info):
        """
        Add a new pkgname::pkgname INTERFACE target that depends on default_components or
        on all other library targets (not exes)
        It will not be added if there exists already a pkgname::pkgname target (Or an alias exists).
        """
        root_target_name = self._get_cmake_target_name()
        # TODO: What if an exe target is called like the pkg_name::pkg_name
        if libs and root_target_name not in libs:
            # Add a generic interface target for the package depending on the others
            if cpp_info.default_components is not None:
                all_requires = {}
                for defaultc in cpp_info.default_components:
                    comp_name = self._get_cmake_target_name(comp_name=defaultc)
                    link_feature = self._cmake_prop(self._conanfile.ref.name, "cmake_link_feature",
                                                    defaultc)
                    all_requires[comp_name] = {
                        "link": True,  # It is an interface, full link
                        "link_feature": link_feature
                    }
            else:
                all_requires = {k: {
                    "link": True,
                    "link_feature": self._cmake_prop(self._conanfile.ref.name, "cmake_link_feature",
                                                     v.get("comp_name"))
                }
                    for k, v in libs.items()}
            # This target might have an alias, so we need to check it
            cmake_target_aliases = self._get_aliases()
            libs[root_target_name] = {"type": "INTERFACE",
                                      "requires": all_requires,
                                      "cmake_target_aliases": cmake_target_aliases}

    def _get_exes(self, cpp_info):
        exes = {}

        if cpp_info.has_components:
            for name, comp in cpp_info.components.items():
                if comp.exe or comp.type is PackageType.APP:
                    target = self._get_cmake_target_name(comp_name=name)
                    exe_location = self._path(comp.location)
                    exes[target] = exe_location
        else:
            if cpp_info.exe:
                target = self._get_cmake_target_name()
                exe_location = self._path(cpp_info.location)
                exes[target] = exe_location

        return exes

    def _path(self, p):
        def escape(p_):
            return p_.replace("$", "\\$").replace('"', '\\"')

        p = p.replace("\\", "/")
        if os.path.isabs(p):
            if p.startswith(self._pkg_folder):
                rel = p[len(self._pkg_folder):].lstrip("/")
                return f"${{{self._pkg_folder_var}}}/{escape(rel)}"
            return escape(p)
        return f"${{{self._pkg_folder_var}}}/{escape(p)}"

    @property
    def _template(self):
        # TODO: CMake 3.24: Apple Frameworks: https://cmake.org/cmake/help/latest/manual/cmake-generator-expressions.7.html#genex:LINK_LIBRARY
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
        {% for alias in lib_info.get("cmake_target_aliases", []) %}
        if(NOT TARGET {{alias}})
            message(STATUS "Conan: Target declared alias '{{alias}}' for '{{lib}}'")
            add_library({{alias}} ALIAS {{lib}})
        endif()
        {% endfor %}
        {% if lib_info.get("includedirs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                     {{config_wrapper(config, lib_info["includedirs"])}})
        {% endif %}
        {% if lib_info.get("defines") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_DEFINITIONS
                     "{{config_wrapper(config, lib_info["defines"])}}")
        {% endif %}
        {% if lib_info.get("cxxflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     "$<$<COMPILE_LANGUAGE:CXX>:{{config_wrapper(config, lib_info["cxxflags"])}}>")
        {% endif %}
        {% if lib_info.get("cflags") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                     "$<$<COMPILE_LANGUAGE:C>:{{config_wrapper(config, lib_info["cflags"])}}>")
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
        if("CXX" IN_LIST _languages)
            list(APPEND _languages "C")
        endif()
        if("CUDA" IN_LIST _languages)
            list(APPEND _languages "C" "CXX")
        endif()
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
        {% if lib_info.get("no_soname") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_NO_SONAME_{{config}} TRUE)
        {% endif %}
        {% elif lib_info.get("type") == "INTERFACE" %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        {% endif %}
        {% if lib_info.get("link_location") %}
        set_target_properties({{lib}} PROPERTIES IMPORTED_IMPLIB_{{config}}
                              "{{lib_info["link_location"]}}")
        {% endif %}

        {% if lib_info.get("requires") %}
        # Information of transitive dependencies
        {% for require_target, link_info in lib_info["requires"].items() %}

        # Requirement {{lib}} -> {{require_target}} (Full link: {{link_info["link"]}})
        {% if link_info["link"] %}
        {% if link_info["link_feature"] %}
        # Link feature: {{link_info["link_feature"]}}
        if(CMAKE_VERSION VERSION_LESS "3.24")
            message(FATAL_ERROR "The 'CMakeConfigDeps' generator LINK_FEATURE property only works with CMake >= 3.24")
        endif()
        {% endif %}
        # set property allows to append, and lib_info[requires] will iterate
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
            {% if link_info["link_feature"] %}
                     "$<LINK_LIBRARY:{{link_info["link_feature"]}},{{config_wrapper(config, require_target)}}>")
            {% else %}
                     "{{config_wrapper(config, require_target)}}")
            {% endif %}
        {% else %}
        if(CMAKE_VERSION VERSION_LESS "3.27")
            message(FATAL_ERROR "The 'CMakeConfigDeps' generator COMPILE_ONLY expression only works with CMake >= 3.27")
        endif()
        # If the headers trait is not there, this will do nothing
        target_link_libraries({{lib}} INTERFACE
                              $<COMPILE_ONLY:{{config_wrapper(config, require_target)}}> )
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_LINK_DEPENDENT_LIBRARIES_{{config}}
                     {{require_target}})
        {% endif %}
        {% endfor %}
        {% endif %}

        {% if lib_info.get("system_libs") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                     {{config_wrapper(config, lib_info["system_libs"])}})
        {% endif %}
        {% if lib_info.get("frameworks") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_LINK_LIBRARIES
                     "{{config_wrapper(config, lib_info["frameworks"])}}")
        {% endif %}
        {% if lib_info.get("package_framework") %}
        set_property(TARGET {{lib}} APPEND PROPERTY IMPORTED_CONFIGURATIONS {{config}})
        set_target_properties({{lib}} PROPERTIES
            IMPORTED_LOCATION_{{config}} "{{lib_info["package_framework"]["location"]}}"
            FRAMEWORK TRUE)
        if(CMAKE_VERSION VERSION_LESS "3.24")
            set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                         $<$<COMPILE_LANGUAGE:CXX>:-F{{lib_info["package_framework"]["frameworkdir"]}}>)
            set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_COMPILE_OPTIONS
                         $<$<COMPILE_LANGUAGE:C>:-F{{lib_info["package_framework"]["frameworkdir"]}}>)
        endif()
        {% endif %}

        {% if lib_info.get("sources") %}
        set_property(TARGET {{lib}} APPEND PROPERTY INTERFACE_SOURCES
                     {{config_wrapper(config, lib_info["sources"] )}})
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
