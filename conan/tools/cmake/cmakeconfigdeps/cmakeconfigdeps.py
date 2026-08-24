import glob
import os
import re
import textwrap

from jinja2 import Template

from conan.api.output import Color, ConanOutput
from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.api.install.generators import relativize_path
from conan.internal.model.dependencies import get_transitive_requires
from conan.internal.model.pkg_type import PackageType
from conan.tools.cmake.cmakeconfigdeps.config import ConfigTemplate2
from conan.tools.cmake.cmakeconfigdeps.config_version import ConfigVersionTemplate2
from conan.tools.cmake.cmakeconfigdeps.target_configuration import TargetConfigurationTemplate2
from conan.tools.cmake.cmakeconfigdeps.targets import TargetsTemplate2
from conan.tools.cmake.utils import cmake_escape_value, parse_extra_variable
from conan.tools.files import save
from conan.internal.util.files import load

FIND_MODE_MODULE = "module"
FIND_MODE_CONFIG = "config"
FIND_MODE_NONE = "none"
FIND_MODE_BOTH = "both"


class CMakeConfigDeps:

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile
        self.configuration = str(self._conanfile.settings.build_type)

        # These are just for legacy compatibility, but not use at al
        self._build_context_activated = []
        self._build_context_build_modules = []
        self._build_context_suffix = {}
        # Enable/Disable checking if a component target exists or not
        self._check_components_exist = False

        self._properties = {}

    @property
    def build_context_activated(self):
        return self._build_context_activated

    @build_context_activated.setter
    def build_context_activated(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_activated is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_activated = value

    @property
    def build_context_build_modules(self):
        return self._build_context_build_modules

    @build_context_build_modules.setter
    def build_context_build_modules(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_build_modules is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_build_modules = value

    @property
    def build_context_suffix(self):
        return self._build_context_suffix

    @build_context_suffix.setter
    def build_context_suffix(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.build_context_suffix is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._build_context_suffix = value

    @property
    def check_components_exist(self):
        return self._check_components_exist

    @check_components_exist.setter
    def check_components_exist(self, value):
        self._conanfile.output.warning("CMakeConfigDeps.check_components_exist is deprecated, "
                                       "not used anymore", warn_tag="deprecated")
        self._check_components_exist = value

    def generate(self):
        """
        This method will save the generated files to the ``conanfile.generators_folder`` folder
        """
        self._conanfile.output.warning("CMakeConfigDeps is experimental, and might get "
                                       "breaking changes in future releases",
                                       warn_tag="experimental")
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(self._conanfile, generator_file, content)
        _PathGenerator(self, self._conanfile).generate()

    def _content(self):
        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test

        # Iterate all the transitive requires
        ret = {}
        direct_deps = []
        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            cmake_find_mode = self.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()
            if cmake_find_mode == FIND_MODE_NONE:
                continue
            if cmake_find_mode in (FIND_MODE_MODULE, FIND_MODE_BOTH):
                ConanOutput(self._conanfile.ref).warning("CMakeConfigDeps does not support "
                                                         f"module find mode in {dep}.\n"
                                                         f"Config mode will be used regardless.",
                                                         # Should this be risk?
                                                         warn_tag="deprecated")

            if require.direct:
                direct_deps.append((require, dep))
            # Shared files (config, config-version, targets) have a context-independent
            # filename. When the same package is both requires and tool_requires, keep the
            # host-context version so legacy variables (<pkg>_LIBRARIES, ...) are preserved.
            context_gen = _CMakeContextGenerator(self, require, dep)
            config_version_filename, config_version_context = context_gen.get_config_version_info()
            if config_version_filename not in ret:
                config_version = ConfigVersionTemplate2(config_version_filename, config_version_context)
                ret[config_version.filename] = config_version.content()
            config_filename, config_context = context_gen.get_config_info()
            if config_filename not in ret:
                config = ConfigTemplate2(config_filename, config_context)
                ret[config.filename] = config.content()
            targets_filename, targets_context = context_gen.get_targets_info()
            if targets_filename not in ret:
                targets = TargetsTemplate2(targets_filename, targets_context)
                ret[targets.filename] = targets.content()
            target_filename, target_context = context_gen.get_target_configuration_info()
            target_configuration = TargetConfigurationTemplate2(target_filename, target_context)
            ret[target_configuration.filename] = target_configuration.content()

        self._print_help(direct_deps)
        return ret

    def _print_help(self, direct_deps):
        if direct_deps:
            msg = ["CMakeDeps necessary find_package() and targets for your CMakeLists.txt"]
            link_targets = []
            for (require, dep) in direct_deps:
                note = " # Optional. This is a tool-require, can't link its targets" \
                    if require.build else ""
                msg.append(f"    find_package({self.get_cmake_filename(dep)}){note}")
                if not require.build and not dep.cpp_info.exe:
                    target_name = self.get_property("cmake_target_name", dep)
                    link_targets.append(target_name or f"{dep.ref.name}::{dep.ref.name}")
            if link_targets:
                msg.append(f"    target_link_libraries(... {' '.join(link_targets)})")
            self._conanfile.output.info("\n".join(msg), fg=Color.CYAN)

    def set_property(self, dep, prop, value, build_context=False):
        """
        Using this method you can overwrite the :ref:`property<CMakeConfigDeps Properties>` values
        set by the Conan recipes from the consumer.

        :param dep: Name of the dependency to set the :ref:`property<CMakeConfigDeps Properties>`.
         For components use the syntax: ``dep_name::component_name``.
        :param prop: Name of the :ref:`property<CMakeDeps Properties>`.
        :param value: Value of the property. Use ``None`` to invalidate any value set by the
         upstream recipe.
        :param build_context: Set to ``True`` if you want to set the property for a dependency that
         belongs to the build context (``False`` by default).
        """
        build_suffix = "&build" if build_context else ""
        self._properties.setdefault(f"{dep}{build_suffix}", {}).update({prop: value})

    def get_property(self, prop, dep, comp_name=None, check_type=None):
        dep_name = dep.ref.name
        # Find the requirement that points to this "dep".
        # TODO: It would probably be more explicit if it was an argument as "dep", but to keep
        #   diff minimal
        require = next(iter(r for r, d in self._conanfile.dependencies.items() if d is dep))
        build_suffix = "&build" if require.build else ""
        dep_comp = f"{str(dep_name)}::{comp_name}" if comp_name else f"{str(dep_name)}"
        try:
            value = self._properties[f"{dep_comp}{build_suffix}"][prop]
            if check_type is not None and not isinstance(value, check_type):
                raise ConanException(f'The expected type for {prop} is "{check_type.__name__}", '
                                     f'but "{type(value).__name__}" was found')
            return value
        except KeyError:
            # Here we are not using the cpp_info = deduce_cpp_info(dep) because it is not
            # necessary for the properties
            if not comp_name:
                return dep.cpp_info.get_property(prop, check_type=check_type)
            comp = dep.cpp_info.components.get(comp_name)  # it is a default dict
            if comp is not None:
                return comp.get_property(prop, check_type=check_type)

    def get_cmake_filename(self, dep):
        # Get the name of the file for the find_package(XXX)
        # This is used by CMakeDeps to determine:
        # - The filename to generate (XXX-config.cmake or FindXXX.cmake)
        # - The name of the defined XXX_DIR variables
        # - The name of transitive dependencies for calls to find_dependency
        ret = self.get_property("cmake_file_name", dep)
        return ret or dep.ref.name


class _CMakeContextGenerator:
    """Builds filenames and Jinja contexts for one dependency requirement."""

    def __init__(self, cmakedeps, require, dep):
        self.cmakedeps = cmakedeps
        self.consumer_conanfile = cmakedeps._conanfile
        self.require = require
        self.dep = dep
        self.full_cpp_info = dep.cpp_info.deduce_full_cpp_info(dep)
        self.base_filename = cmakedeps.get_cmake_filename(dep)
        self.is_build_context = require.build
        # Prepared to filter transitive tool-requires with visible=True
        self.transitive_reqs = get_transitive_requires(self.consumer_conanfile, dep)

        build_type = dep.settings.get_safe(
            "build_type", str(self.consumer_conanfile.settings.build_type))
        self.build_type = build_type
        self.config = build_type.upper() if build_type else None
        config_folder = f"_{self.config}" if self.config else ""
        build_suffix = "_BUILD" if self.is_build_context else ""
        self.pkg_folder = dep.package_folder.replace("\\", "/")
        self.pkg_folder_var = f"{dep.ref.name}_PACKAGE_FOLDER{config_folder}{build_suffix}"

    def get_property(self, prop, dep=None, comp_name=None, check_type=None):
        return self.cmakedeps.get_property(prop, dep or self.dep, comp_name, check_type)

    def get_cmake_filename(self, dep=None):
        if dep is None:
            return self.base_filename
        return self.cmakedeps.get_cmake_filename(dep)

    def get_cmake_target_name(self, dep=None, comp_name=None):
        dep = dep or self.dep
        target_name = self.get_property("cmake_target_name", dep, comp_name)
        default = (f"{dep.ref.name}::{comp_name}" if comp_name
                   else f"{dep.ref.name}::{dep.ref.name}")
        return target_name or default

    def get_config_version_info(self):
        return self._ConfigVersion(self).info()

    def get_config_info(self):
        return self._Config(self).info()

    def get_targets_info(self):
        return self._Targets(self).info()

    def get_target_configuration_info(self):
        return self._TargetConfiguration(self).info()

    class _ConfigVersion:
        """Filename + context for ConfigVersionTemplate2."""

        def __init__(self, ctx):
            self._ctx = ctx

        def info(self):
            f = self._ctx.base_filename
            filename = f"{f}-config-version.cmake" if f == f.lower() else f"{f}ConfigVersion.cmake"
            policy = self._ctx.get_property("cmake_config_version_compat")
            if policy is None:
                policy = "SameMajorVersion"
            if policy not in ("AnyNewerVersion", "SameMajorVersion", "SameMinorVersion",
                              "ExactVersion"):
                raise ConanException(
                    f"Unknown cmake_config_version_compat={policy} in {self._ctx.dep.ref}")
            version = (self._ctx.get_property("system_package_version")
                       or self._ctx.dep.ref.version)
            return filename, {"version": version, "policy": policy}

    class _Config:
        """Filename + context for ConfigTemplate2."""

        def __init__(self, ctx):
            self._ctx = ctx

        def info(self):
            f = self._ctx.base_filename
            filename = f"{f}-config.cmake" if f == f.lower() else f"{f}Config.cmake"
            dep = self._ctx.dep

            conf_extra_variables = dep.conf.get("tools.cmake.cmaketoolchain:extra_variables",
                                                default={}, check_type=dict)
            dep_extra_variables = self._ctx.get_property("cmake_extra_variables",
                                                         check_type=dict) or {}
            # The configuration variables have precedence over the dependency ones
            # (those already appear on the toolchain files)
            cmake_extra_variables = {k: v for k, v in dep_extra_variables.items()
                                     if k not in conf_extra_variables}
            parsed_extra_variables = {}
            for key, value in cmake_extra_variables.items():
                parsed_extra_variables[key] = parse_extra_variable("cmake_extra_variables",
                                                                   key, value)

            cmake_components = self._ctx.get_property("cmake_components", check_type=list)
            if cmake_components is None:
                cmake_components = []
                # This assumes cmake_components is only defined with not multi .libs=[lib1, lib2]
                for name in dep.cpp_info.components:
                    if name.startswith("_"):  # Skip private components
                        continue
                    comp_components = self._ctx.get_property("cmake_components", comp_name=name,
                                                             check_type=list)
                    if comp_components:
                        cmake_components.extend(comp_components)
                    else:
                        cmakename = self._ctx.get_property("cmake_target_name", comp_name=name)
                        if cmakename and "::" in cmakename:  # Remove package namespace
                            cmakename = cmakename.split("::", 1)[1]
                        cmake_components.append(cmakename or name)
            components = " ".join(cmake_components) if cmake_components else ""

            build_modules_paths = self._ctx.get_property("cmake_build_modules",
                                                         check_type=list) or []
            # FIXME: Proper escaping of paths for CMake and relativization
            # FIXME: build_module_paths coming from last config only
            build_modules_paths = [p.replace("\\", "/") for p in build_modules_paths]
            build_modules_paths = [relativize_path(p, self._ctx.consumer_conanfile,
                                                   "${CMAKE_CURRENT_LIST_DIR}")
                                   for p in build_modules_paths]

            context = {"filename": f,
                       "components": components,
                       "pkg_name": dep.ref.name,
                       "targets_include_file": f"{f}Targets.cmake",
                       "build_modules_paths": build_modules_paths,
                       "extra_variables": parsed_extra_variables}
            context.update(self._get_legacy_vars())
            return filename, context

        def _get_legacy_vars(self):
            # Auxiliary variables for legacy consumption and try_compile cases
            prefixes = self._ctx.get_property("cmake_additional_variables_prefixes",
                                              check_type=list) or []
            prefixes = [self._ctx.base_filename] + prefixes

            include_dirs = definitions = libraries = None
            if not self._ctx.is_build_context:  # try_compile and legacy globals
                aggregated_cppinfo = self._ctx.full_cpp_info.aggregated_components()
                # FIXME: Proper escaping of paths for CMake
                incdirs = [relativize_path(i.replace("\\", "/"), self._ctx.consumer_conanfile,
                                           "${CMAKE_CURRENT_LIST_DIR}")
                           for i in aggregated_cppinfo.includedirs]
                include_dirs = ";".join(incdirs)
                definitions = ";".join("-D" + cmake_escape_value(d)
                                       for d in aggregated_cppinfo.defines)
                libs = []
                if self._ctx.full_cpp_info.has_components:
                    for component in self._ctx.full_cpp_info.components.keys():
                        libs.append(self._ctx.get_cmake_target_name(comp_name=component))
                else:
                    libs.append(self._ctx.get_cmake_target_name())
                libraries = " ".join(libs) if libs else ""

            return {"additional_variables_prefixes": prefixes,
                    "version": self._ctx.dep.ref.version,
                    "include_dirs": include_dirs,
                    "definitions": definitions,
                    "libraries": libraries}

    class _Targets:
        """Filename + context for TargetsTemplate2."""

        def __init__(self, ctx):
            self._ctx = ctx

        def info(self):
            f = self._ctx.base_filename
            return f"{f}Targets.cmake", {"filename": f, "ref": str(self._ctx.dep.ref)}

    class _TargetConfiguration:
        """Filename + context for TargetConfigurationTemplate2."""

        def __init__(self, ctx):
            self._ctx = ctx

        def info(self):
            assert isinstance(self._ctx.full_cpp_info.type, PackageType)

            dependencies, cpp_info_requires = self._get_dependencies_and_requires()

            libs = {}
            # The BUILD context does not generate libraries targets atm
            if not self._ctx.is_build_context:
                libs = self._get_libs(cpp_info_requires)
                self._add_root_lib_target(libs)

            exes = self._get_exes()
            self._validate_lib_aliases(libs)

            pkg_folder_rel = relativize_path(self._ctx.pkg_folder, self._ctx.consumer_conanfile,
                                             "${CMAKE_CURRENT_LIST_DIR}")
            context = {"dependencies": dependencies,
                       "pkg_folder": pkg_folder_rel,
                       "pkg_folder_var": self._ctx.pkg_folder_var,
                       "config": self._ctx.config,
                       "exes": exes,
                       "libs": libs,
                       "context": self._ctx.dep.context}

            config_name = (self._ctx.build_type or "none").lower()
            build = "Build" if self._ctx.is_build_context else ""
            filename = f"{self._ctx.base_filename}-Targets{build}-{config_name}.cmake"
            return filename, context

        def _get_dependencies_and_requires(self):
            transitive_reqs = self._ctx.transitive_reqs
            def _get_dep_find_mode(d):
                find_mode = self._ctx.get_property("cmake_find_mode", d)

                if find_mode is None:
                    find_mode = FIND_MODE_CONFIG

                return "" if find_mode.lower() in (FIND_MODE_NONE, FIND_MODE_BOTH) else find_mode.upper()
            dependencies = {self._ctx.get_cmake_filename(d): _get_dep_find_mode(d)
                            for d in transitive_reqs.values()}
            extra_mods = self._ctx.get_property("cmake_extra_dependencies", check_type=list) or []
            dependencies.update({extra_mod: "" for extra_mod in extra_mods})

            requires = {}
            full_cpp_info = self._ctx.full_cpp_info
            if full_cpp_info.has_components:
                for name, component in full_cpp_info.components.items():
                    requires[name] = self._get_component_requires(
                        component, full_cpp_info.components)
            else:
                requires[None] = self._get_component_requires(full_cpp_info, None)
            return dependencies, requires

        def _get_component_requires(self, info, components):
            result = {}
            requires = info.parsed_requires()
            pkg_type = info.type
            assert isinstance(pkg_type, PackageType), f"Pkg type {pkg_type} {type(pkg_type)}"
            dep = self._ctx.dep
            transitive_reqs = self._ctx.transitive_reqs

            if not requires and not components:  # global cpp_info without components definition
                # require the pkgname::pkgname base (user defined) or INTERFACE base target
                for req, d in transitive_reqs.items():
                    if d.package_type is PackageType.APP:
                        continue
                    dep_target = self._ctx.get_cmake_target_name(d)
                    link_feature = self._ctx.get_property("cmake_link_feature", d)
                    result[dep_target] = {
                        "link": req.libs,
                        "link_feature": link_feature
                    }
                return result

            for required_pkg, required_comp in requires:
                if required_pkg is None:  # Points to a component of same package
                    dep_comp = components.get(required_comp)
                    assert dep_comp, f"Component {required_comp} not found in {dep}"
                    dep_target = self._ctx.get_cmake_target_name(comp_name=required_comp)
                    link_feature = self._ctx.get_property("cmake_link_feature",
                                                     comp_name=required_comp)
                    result[dep_target] = {
                        "link": True,  # Components of same package have PUBLIC dependency
                        "link_feature": link_feature
                    }
                else:  # Different package
                    try:
                        req, transitive_dep = transitive_reqs.of(required_pkg)
                    except KeyError:  # The transitive dep might have been skipped
                        pass
                    else:
                        # To check if the component exist, it is ok to use the standard cpp_info
                        # No need to use the cpp_info = deduce_cpp_info(dep)
                        dep_comp = transitive_dep.cpp_info.components.get(required_comp)
                        if dep_comp is None:
                            # It must be the interface pkgname::pkgname target
                            if required_pkg != required_comp:
                                msg = (f"{dep} recipe cpp_info did .requires to "
                                       f"'{required_pkg}::{required_comp}' but component "
                                       f"'{required_comp}' not found in {required_pkg}")
                                raise ConanException(msg)
                            if transitive_dep.package_type is PackageType.APP:
                                continue  # It doesn't make sense to link a package that is an App
                            comp = None
                            # replace_requires
                            default_target = (f"{transitive_dep.ref.name}::"
                                              f"{transitive_dep.ref.name}")
                            link = req.libs  # Do what the requirement to that package says
                        else:
                            if dep_comp.type is PackageType.APP or dep_comp.exe:
                                continue  # It doesn't make sense to link a package that is an App
                            comp = required_comp
                            default_target = f"{required_pkg}::{required_comp}"
                            # requirement of a specific component of the other package;
                            # the other package can be an APP containing a LIB component
                            # (libtool->automake(app) case) and req.libs may not be defined
                            link = not (pkg_type is PackageType.SHARED and
                                        dep_comp.type is PackageType.SHARED)
                        link = req.libs or link
                        dep_target = self._ctx.get_property("cmake_target_name", transitive_dep, comp)
                        dep_target = dep_target or default_target
                        link_feature = self._ctx.get_property("cmake_link_feature", transitive_dep, comp)

                        result[dep_target] = {
                            "link": link,
                            "link_feature": link_feature
                        }
            return result

        def _get_libs(self, cpp_info_requires):
            libs = {}
            cpp_info = self._ctx.full_cpp_info
            if cpp_info.has_components:
                for name, component in cpp_info.components.items():
                    target_name = self._ctx.get_cmake_target_name(comp_name=name)
                    target = self._get_cmake_lib(component, cpp_info_requires, comp_name=name)
                    if target is not None:
                        target["cmake_target_aliases"] = self._get_aliases(name)
                        libs[target_name] = target
            else:
                target_name = self._ctx.get_cmake_target_name()
                target = self._get_cmake_lib(cpp_info, cpp_info_requires)
                if target is not None:
                    target["cmake_target_aliases"] = self._get_aliases()
                    libs[target_name] = target
            return libs

        def _get_cmake_lib(self, info, cpp_info_requires, comp_name=None):
            if info.exe or not (info.package_framework or info.frameworks or info.includedirs
                                or info.libs or info.system_libs or info.defines or info.requires):
                return

            includedirs = ";".join(self._cmake_pkg_path(i)
                                   for i in info.includedirs) if info.includedirs else ""
            requires = cpp_info_requires[comp_name]
            assert isinstance(requires, dict)
            defines = ";".join(cmake_escape_value(f) for f in info.defines)
            # FIXME: Filter by lib traits!!!!!
            if not self._ctx.require.headers:  # If not depending on headers, paths and
                includedirs = defines = None
            extra_libs = self._ctx.get_property("cmake_extra_interface_libs", comp_name=comp_name,
                                           check_type=list) or []
            sources = [self._cmake_pkg_path(source) for source in info.sources]
            target = {"type": "INTERFACE",
                      "comp_name": comp_name,
                      "includedirs": includedirs,
                      "defines": defines,
                      "requires": requires,
                      "cxxflags": ";".join(cmake_escape_value(f) for f in info.cxxflags),
                      "cflags": ";".join(cmake_escape_value(f) for f in info.cflags),
                      "sharedlinkflags": ";".join(cmake_escape_value(v)
                                                  for v in info.sharedlinkflags),
                      "exelinkflags": ";".join(cmake_escape_value(v) for v in info.exelinkflags),
                      "system_libs": " ".join(info.system_libs + extra_libs),
                      "sources": " ".join(sources)
                      }
            # System frameworks (only Apple OS)
            if info.frameworks:
                target['frameworks'] = " ".join([f"-framework {frw}" for frw in info.frameworks])
            # FIXME: Ignoring this value for now. Relies on cmake_target_name or lib name.
            #        Revisit when cpp.exe value is used too.
            if info.package_framework:
                assert isinstance(info.package_framework, str), \
                    f"package_framework should be a str"
                if info.libs:
                    raise ConanException("Can't define .libs and .package_framework for the same "
                                         "component")
                target["package_framework"] = {}
                lib_type = "SHARED" if info.type is PackageType.SHARED else \
                    "STATIC" if info.type is PackageType.STATIC else "STATIC"
                assert lib_type, f"Unknown package type {info.type}"
                assert info.location, \
                    f"cpp_info.location missing for framework {info.package_framework}"
                target["type"] = lib_type
                target["package_framework"]["location"] = self._cmake_pkg_path(info.location)
                # empty as frameworks have their own way to inject headers
                target["includedirs"] = []
                # FIXME: Not needed for CMake < 3.24. Remove when Conan requires CMake >= 3.24
                target["package_framework"]["frameworkdir"] = self._cmake_pkg_path(self._ctx.pkg_folder)
            if info.libs:
                if len(info.libs) != 1:
                    raise ConanException(f"New CMakeDeps only allows 1 lib per component:\n"
                                         f"{self._ctx.dep}: {info.libs}")
                assert info.location, "info.location missing for .libs, it should have been deduced"
                location = self._cmake_pkg_path(info.location)
                link_location = (self._cmake_pkg_path(info.link_location)
                                 if info.link_location else None)
                lib_type = "SHARED" if info.type is PackageType.SHARED else \
                    "STATIC" if info.type is PackageType.STATIC else None
                assert lib_type, f"Unknown package type {info.type}"
                target["type"] = lib_type
                target["location"] = location
                target["link_location"] = link_location
                link_languages = info.languages or self._ctx.dep.languages or []
                link_languages = ["CXX" if c == "C++" else c for c in link_languages]
                target["link_languages"] = link_languages
                if lib_type == "SHARED" and self._ctx.get_property("nosoname", comp_name=comp_name,
                                                              check_type=bool):
                    target["no_soname"] = True
            return target

        def _get_aliases(self, comp_name=None):
            return self._ctx.get_property("cmake_target_aliases", comp_name=comp_name,
                                     check_type=list) or []

        def _add_root_lib_target(self, libs):
            """
            Add a new pkgname::pkgname INTERFACE target that depends on default_components or
            on all other library targets (not exes)
            It will not be added if there exists already a pkgname::pkgname target
            (Or an alias exists).
            """
            root_target_name = self._ctx.get_cmake_target_name()
            cpp_info = self._ctx.full_cpp_info
            # TODO: What if an exe target is called like the pkg_name::pkg_name
            if libs and root_target_name not in libs:
                # Add a generic interface target for the package depending on the others
                if cpp_info.default_components is not None:
                    all_requires = {}
                    for defaultc in cpp_info.default_components:
                        comp_name = self._ctx.get_cmake_target_name(comp_name=defaultc)
                        link_feature = self._ctx.get_property("cmake_link_feature",
                                                         comp_name=defaultc)
                        all_requires[comp_name] = {
                            "link": True,  # It is an interface, full link
                            "link_feature": link_feature
                        }
                else:
                    all_requires = {k: {
                        "link": True,
                        "link_feature": self._ctx.get_property("cmake_link_feature",
                                                          comp_name=v.get("comp_name"))
                    }
                        for k, v in libs.items()}
                # This target might have an alias, so we need to check it
                libs[root_target_name] = {"type": "INTERFACE",
                                          "requires": all_requires,
                                          "cmake_target_aliases": self._get_aliases()}

        def _get_exes(self):
            exes = {}
            cpp_info = self._ctx.full_cpp_info
            if cpp_info.has_components:
                for name, comp in cpp_info.components.items():
                    if comp.exe or comp.type is PackageType.APP:
                        target = self._ctx.get_cmake_target_name(comp_name=name)
                        exes[target] = self._cmake_pkg_path(comp.location)
            else:
                if cpp_info.exe:
                    target = self._ctx.get_cmake_target_name()
                    exes[target] = self._cmake_pkg_path(cpp_info.location)
            return exes

        def _validate_lib_aliases(self, libs):
            seen_aliases = set()
            root_target_name = self._ctx.get_cmake_target_name()
            for lib in libs.values():
                for alias in lib.get("cmake_target_aliases", []):
                    if alias == root_target_name:
                        raise ConanException(
                            f"Can't define an alias '{alias}' for the "
                            f"root target '{root_target_name}' in {self._ctx.dep}. "
                            f"Changing the default target should be done with the "
                            f"'cmake_target_name' property.")
                    if alias in seen_aliases:
                        raise ConanException(f"Alias '{alias}' already defined in {self._ctx.dep}. ")
                    seen_aliases.add(alias)
                    if alias in libs:
                        raise ConanException(
                            f"Alias '{alias}' already defined as a target in {self._ctx.dep}. ")

        def _cmake_pkg_path(self, p):
            def escape(p_):
                return p_.replace("$", "\\$").replace('"', '\\"')

            p = p.replace("\\", "/")
            if os.path.isabs(p):
                if p.startswith(self._ctx.pkg_folder):
                    rel = p[len(self._ctx.pkg_folder):].lstrip("/")
                    return f"${{{self._ctx.pkg_folder_var}}}/{escape(rel)}"
                return escape(p)
            return f"${{{self._ctx.pkg_folder_var}}}/{escape(p)}"


# TODO: Repeated from CMakeToolchain blocks
def _join_paths(conanfile, paths):
    paths = [p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"') for p in paths]
    paths = [relativize_path(p, conanfile, "${CMAKE_CURRENT_LIST_DIR}") for p in paths]
    return " ".join([f'"{p}"' for p in paths])


class _PathGenerator:
    _conan_cmakedeps_paths = "conan_cmakedeps_paths.cmake"

    def __init__(self, cmakedeps, conanfile):
        self._conanfile = conanfile
        self._cmakedeps = cmakedeps

    def _get_cmake_paths(self, requirements, dirs_name):
        paths = {}
        cmake_vars = {
            "bindirs": "CMAKE_PROGRAM_PATH",
            "libdirs": "CMAKE_LIBRARY_PATH",
            "includedirs": "CMAKE_INCLUDE_PATH",
            "frameworkdirs": "CMAKE_FRAMEWORK_PATH",
            "builddirs": "CMAKE_MODULE_PATH"
        }
        for req, dep in requirements:
            cppinfo = dep.cpp_info.aggregated_components()
            cppinfo_dirs = getattr(cppinfo, dirs_name, [])
            if not cppinfo_dirs:
                continue
            previous = paths.get(req.ref.name)
            if previous:
                self._conanfile.output.info(f"There is already a '{req.ref}' package contributing"
                                            f" to {cmake_vars[dirs_name]}. Using the one"
                                            f" defined by the context={dep.context}.")
            paths[req.ref.name] = cppinfo_dirs
        return [d for dirs in paths.values() for d in dirs]

    def generate(self):
        template = textwrap.dedent("""\
        set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)

        {% for pkg_name, folder in pkg_paths.items() %}
        set({{pkg_name}}_DIR "{{folder}}")
        {% endfor %}
        {% for pkg_name, folders in pkg_paths_multi.items() %}
        {% for folder in folders %}
        list(APPEND CONAN_{{pkg_name}}_DIR_MULTI "{{folder}}")
        {% endfor %}
        {% endfor %}
        {% if host_runtime_dirs %}
        set(CONAN_RUNTIME_LIB_DIRS {{ host_runtime_dirs }} )
        # Only for VS, needs CMake>=3.27
        set(CMAKE_VS_DEBUGGER_ENVIRONMENT "PATH=${CONAN_RUNTIME_LIB_DIRS};%PATH%")
        {% endif %}
        {% if cmake_program_path %}
        list(PREPEND CMAKE_PROGRAM_PATH {{ cmake_program_path }})
        {% endif %}
        {% if cmake_library_path %}
        list(PREPEND CMAKE_LIBRARY_PATH {{ cmake_library_path }})
        {% endif %}
        {% if cmake_include_path %}
        list(PREPEND CMAKE_INCLUDE_PATH {{ cmake_include_path }})
        {% endif %}
        {% if cmake_framework_path %}
        list(PREPEND CMAKE_FRAMEWORK_PATH {{ cmake_framework_path }})
        {% endif %}
        # Definition of CMAKE_MODULE_PATH to be able to include(module)
        {% if cmake_module_path %}
        list(PREPEND CMAKE_MODULE_PATH {{ cmake_module_path }})
        {% endif %}
        """)
        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.direct_build
        test_req = self._conanfile.dependencies.test
        host_test_reqs = list(host_req.items()) + list(test_req.items())
        all_reqs = host_test_reqs + list(build_req.items())
        # gen_folder = self._conanfile.generators_folder.replace("\\", "/")
        # if not, test_cmake_add_subdirectory test fails
        # content.append('set(CMAKE_FIND_PACKAGE_PREFER_CONFIG ON)')
        pkg_paths = {}

        pkg_paths_multi = {}
        if os.path.exists(self._conan_cmakedeps_paths):
            existing_toolchain = load(self._conan_cmakedeps_paths)
            pattern_paths = r"list\(APPEND CONAN_([A-Za-z0-9-_]*)_DIR_MULTI \"([^)]*)\"\)"
            variable_match = re.findall(pattern_paths, existing_toolchain)
            for (captured_name, captured_path) in variable_match:
                path_list = pkg_paths_multi.setdefault(captured_name, [])
                if captured_path not in path_list:
                    path_list.append(captured_path)

        for req, dep in all_reqs:
            cmake_find_mode = self._cmakedeps.get_property("cmake_find_mode", dep)
            cmake_find_mode = cmake_find_mode or FIND_MODE_CONFIG
            cmake_find_mode = cmake_find_mode.lower()

            cmake_filename = self._cmakedeps.get_cmake_filename(dep)
            extra_variants = self._cmakedeps.get_property("cmake_file_name_variants", dep,
                                                          check_type=list) or []
            lowercase_variants = {variant.lower() for variant in extra_variants}
            if len(lowercase_variants) > 1:
                raise ConanException(f"'{dep.ref}' 'cmake_file_name_variants' property contains different words. "
                                     "They should be the same with different upper/lower cases only.")
            if lowercase_variants:
                if cmake_filename.lower() not in lowercase_variants:
                    is_cmake_filename_defined = self._cmakedeps.get_property("cmake_file_name", dep) is not None
                    if is_cmake_filename_defined:
                        extra_variants = []
                        msg = (f"'{dep.ref}' 'cmake_file_name_variants' property contains names "
                               f"with different casings than the defined name '{cmake_filename}'. "
                               f"The specified 'cmake_file_name'='{cmake_filename}' property "
                               f"will be used as the only name and the variants will be ignored.")
                        self._conanfile.output.warning(msg)
                    else:
                        msg = (f"'{dep.ref}' 'cmake_file_name_variants' property contains entries "
                               f"that differ from the default 'cmake_file_name'='{cmake_filename}'. "
                               f"They should be the same with different upper/lower cases only.")
                        raise ConanException(msg)
            pkg_names = set([cmake_filename] + extra_variants)
            # https://cmake.org/cmake/help/v3.22/guide/using-dependencies/index.html
            if cmake_find_mode == FIND_MODE_NONE:
                cps = glob.glob(os.path.join(dep.package_folder, f"**/{cmake_filename}.cps"),
                                recursive=True)
                if cps:
                    loc = os.path.dirname(os.path.join(dep.package_folder, cps[0]))
                    loc = loc.replace("\\", "/")
                    relative_path = relativize_path(loc, self._conanfile,
                                                    "${CMAKE_CURRENT_LIST_DIR}")
                    for pkg_name in pkg_names:
                        pkg_paths[pkg_name] = relative_path
                    continue

                try:
                    # This is irrespective of the components, it should be in the root cpp_info
                    # To define the location of the pkg-config.cmake file
                    build_dir = dep.cpp_info.builddirs[0]
                except IndexError:
                    build_dir = dep.package_folder
                pkg_folder = build_dir.replace("\\", "/") if build_dir else None
                if pkg_folder:
                    if any(os.path.isfile(os.path.join(pkg_folder, f + ext)) for f in pkg_names
                           for ext in ("-config.cmake", "Config.cmake")):
                        relative_path = relativize_path(pkg_folder, self._conanfile,
                                                        "${CMAKE_CURRENT_LIST_DIR}")
                        for pkg_name in pkg_names:
                            pkg_paths[pkg_name] = relative_path

                    for pkg_name in pkg_names:
                        existing_paths = pkg_paths_multi.setdefault(pkg_name, [])
                        if pkg_folder not in existing_paths:
                            existing_paths.append(pkg_folder)
                continue

            # If CMakeDeps generated, the folder is this one
            # content.append(f'set({pkg_name}_ROOT "{gen_folder}")')
            for pkg_name in pkg_names:
                pkg_paths[pkg_name] = "${CMAKE_CURRENT_LIST_DIR}"

        # CMAKE_PROGRAM_PATH | CMAKE_LIBRARY_PATH | CMAKE_INCLUDE_PATH
        cmake_program_path = self._get_cmake_paths([(req, dep) for req, dep in all_reqs if req.direct], "bindirs")
        cmake_library_path = self._get_cmake_paths(host_test_reqs, "libdirs")
        cmake_include_path = self._get_cmake_paths(host_test_reqs, "includedirs")
        cmake_framework_path = self._get_cmake_paths(host_test_reqs, "frameworkdirs")
        cmake_module_path = self._get_cmake_paths(all_reqs, "builddirs")
        context = {"host_runtime_dirs": self._get_host_runtime_dirs(),
                   "pkg_paths": pkg_paths,
                   "pkg_paths_multi": pkg_paths_multi,
                   "cmake_program_path": _join_paths(self._conanfile, cmake_program_path),
                   "cmake_library_path": _join_paths(self._conanfile, cmake_library_path),
                   "cmake_include_path": _join_paths(self._conanfile, cmake_include_path),
                   "cmake_framework_path": _join_paths(self._conanfile, cmake_framework_path),
                   "cmake_module_path": _join_paths(self._conanfile, cmake_module_path)
                   }
        content = Template(template, trim_blocks=True, lstrip_blocks=True).render(context)
        save(self._conanfile, self._conan_cmakedeps_paths, content)

    def _get_host_runtime_dirs(self):
        host_runtime_dirs = {}

        # Get the previous configuration
        if os.path.exists(self._conan_cmakedeps_paths):
            existing_toolchain = load(self._conan_cmakedeps_paths)
            pattern_lib_dirs = r"set\(CONAN_RUNTIME_LIB_DIRS ([^)]*)\)"
            variable_match = re.search(pattern_lib_dirs, existing_toolchain)
            if variable_match:
                capture = variable_match.group(1)
                matches = re.findall(r'"\$<\$<CONFIG:([A-Za-z]*)>:([^>]*)>"', capture)
                for config, paths in matches:
                    host_runtime_dirs.setdefault(config, []).append(paths)

        is_win = self._conanfile.settings.get_safe("os") == "Windows"

        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        for req in list(host_req.values()) + list(test_req.values()):
            config = req.settings.get_safe("build_type", self._cmakedeps.configuration)
            aggregated_cppinfo = req.cpp_info.aggregated_components()
            runtime_dirs = aggregated_cppinfo.bindirs if is_win else aggregated_cppinfo.libdirs
            for d in runtime_dirs:
                d = d.replace("\\", "/")
                d = relativize_path(d, self._conanfile, "${CMAKE_CURRENT_LIST_DIR}")
                existing = host_runtime_dirs.setdefault(config, [])
                if d not in existing:
                    existing.append(d)

        return ' '.join(f'"$<$<CONFIG:{c}>:{i}>"' for c, v in host_runtime_dirs.items() for i in v)
