import os
import re
import textwrap
from collections import namedtuple

from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.model.dependencies import get_transitive_requires
from conans.util.files import save


_PCInfo = namedtuple("PCInfo", ['name', 'requires', 'description', 'cpp_info', 'aliases'])


class _PCContentGenerator:

    template = textwrap.dedent("""\
        {% for k, v in pc_variables.items() %}
        {{ "{}={}".format(k, v) }}
        {% endfor %}

        Name: {{ name }}
        Description: {{ description }}
        Version: {{ version }}
        {% if libflags %}
        Libs: {{ libflags }}
        {% endif %}
        {% if cflags %}
        Cflags: {{ cflags }}
        {% endif %}
        {% if requires|length %}
        Requires: {{ requires|join(' ') }}
        {% endif %}
    """)

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep

    def _get_prefix_path(self):
        # If editable, package_folder can be None
        root_folder = self._dep.recipe_folder if self._dep.package_folder is None \
            else self._dep.package_folder
        return root_folder.replace("\\", "/")

    def _get_pc_variables(self, cpp_info):
        """
        Get all the freeform variables defined by Conan and
        users (through ``pkg_config_custom_content``). This last ones will override the
        Conan defined variables.
        """
        prefix_path = self._get_prefix_path()
        pc_variables = {"prefix": prefix_path}
        if cpp_info is None:
            return pc_variables
        # Already formatted directories
        pc_variables.update(self._get_formatted_dirs("libdir", cpp_info.libdirs, prefix_path))
        pc_variables.update(self._get_formatted_dirs("includedir", cpp_info.includedirs, prefix_path))
        pc_variables.update(self._get_formatted_dirs("bindir", cpp_info.bindirs, prefix_path))
        # Get the custom content introduced by user and sanitize it
        custom_content = cpp_info.get_property("pkg_config_custom_content")
        if isinstance(custom_content, dict):
            pc_variables.update(custom_content)
        elif custom_content:  # Legacy: custom content is string
            pc_variable_pattern = re.compile("^(.*)=(.*)")
            for line in custom_content.splitlines():
                match = pc_variable_pattern.match(line)
                if match:
                    key, value = match.group(1).strip(), match.group(2).strip()
                    pc_variables[key] = value
        return pc_variables

    @staticmethod
    def _get_formatted_dirs(folder_name, folders, prefix_path_):
        ret = {}
        for i, directory in enumerate(folders):
            directory = os.path.normpath(directory).replace("\\", "/")
            if directory.startswith(prefix_path_):
                prefix = "${prefix}/"
                directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
            else:
                prefix = "" if os.path.isabs(directory) else "${prefix}/"
            suffix = str(i) if i else ""
            var_name = f"{folder_name}{suffix}"
            ret[var_name] = f"{prefix}{directory}"
        return ret

    def _get_lib_flags(self, libdirvars, cpp_info):
        gnudeps_flags = GnuDepsFlags(self._conanfile, cpp_info)
        libdirsflags = ['-L"${%s}"' % d for d in libdirvars]
        system_libs = ["-l%s" % l for l in (cpp_info.libs + cpp_info.system_libs)]
        shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags
        framework_flags = gnudeps_flags.frameworks + gnudeps_flags.framework_paths
        return " ".join(libdirsflags + system_libs + shared_flags + framework_flags)

    def _get_cflags(self, includedirvars, cpp_info):
        includedirsflags = ['-I"${%s}"' % d for d in includedirvars]
        cxxflags = [var.replace('"', '\\"') for var in cpp_info.cxxflags]
        cflags = [var.replace('"', '\\"') for var in cpp_info.cflags]
        defines = ["-D%s" % var.replace('"', '\\"') for var in cpp_info.defines]
        return " ".join(includedirsflags + cxxflags + cflags + defines)

    def _get_context(self, info):
        pc_variables = self._get_pc_variables(info.cpp_info)
        context = {
            "name": info.name,
            "description": info.description,
            "version": self._dep.ref.version,
            "requires": info.requires,
            "pc_variables": pc_variables,
            "cflags": "",
            "libflags": ""
        }
        if info.cpp_info is not None:
            context.update({
                "version": (info.cpp_info.get_property("component_version") or
                            info.cpp_info.get_property("system_package_version") or
                            self._dep.ref.version),
                "cflags": self._get_cflags([d for d in pc_variables if d.startswith("includedir")],
                                           info.cpp_info),
                "libflags": self._get_lib_flags([d for d in pc_variables if d.startswith("libdir")],
                                                info.cpp_info)
            })
        return context

    def content(self, info):
        assert isinstance(info, _PCInfo)
        context = self._get_context(info)
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return template.render(context)


class _PCGenerator:

    def __init__(self, pkgconfigdeps, require, dep):
        self._conanfile = pkgconfigdeps._conanfile  # noqa
        self._require = require
        self._dep = dep
        self._content_generator = _PCContentGenerator(self._conanfile, self._dep)
        self._transitive_reqs = get_transitive_requires(self._conanfile, dep)
        self._is_build_context = require.build
        self._build_context_folder = pkgconfigdeps.build_context_folder
        self._suffix = pkgconfigdeps.build_context_suffix.get(require.ref.name, "") \
            if self._is_build_context else ""

    def _get_cpp_info_requires_names(self, cpp_info):
        """
        Get all the pkg-config valid names from the requires ones given a CppInfo object.

        For instance, those requires could be coming from:

        ```python
        from conan import ConanFile
        class PkgConfigConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]

            # Or:

            def package_info(self):
                self.cpp_info.components["cmp"].requires = ["other::cmp1"]
        ```
        """
        dep_ref_name = self._dep.ref.name
        ret = []
        for req in cpp_info.requires:
            pkg_ref_name, comp_ref_name = req.split("::") if "::" in req else (dep_ref_name, req)
            # For instance, dep == "hello/1.0" and req == "other::cmp1" -> hello != other
            if dep_ref_name != pkg_ref_name:
                try:
                    req_conanfile = self._transitive_reqs[pkg_ref_name]
                except KeyError:
                    continue  # If the dependency is not in the transitive, might be skipped
            else:  # For instance, dep == "hello/1.0" and req == "hello::cmp1" -> hello == hello
                req_conanfile = self._dep
            comp_name = self._get_component_name(req_conanfile, comp_ref_name)
            if not comp_name:
                pkg_name = self._get_package_name(req_conanfile)
                # Creating a component name with namespace, e.g., dep-comp1
                comp_name = self._get_name_with_namespace(pkg_name, comp_ref_name)
            ret.append(comp_name)
        return ret

    def _components_info(self):
        """
        Get the whole package and its components information like their own requires, names and even
        the cpp_info for each component.

        :return: `list` of `_PCInfo` objects with all the components information
        """
        pkg_name = self._get_package_name(self._dep)
        components_info = []
        # Loop through all the package's components
        for comp_ref_name, cpp_info in self._dep.cpp_info.get_sorted_components().items():
            # At first, let's check if we have defined some components requires, e.g., "dep::cmp1"
            comp_requires_names = self._get_cpp_info_requires_names(cpp_info)
            comp_name = self._get_component_name(self._dep, comp_ref_name)
            if not comp_name:
                comp_name = self._get_name_with_namespace(pkg_name, comp_ref_name)
                comp_description = f"Conan component: {comp_name}"
            else:
                comp_description = f"Conan component: {pkg_name}-{comp_name}"
            comp_aliases = self._get_component_aliases(self._dep, comp_ref_name)
            # Save each component information
            components_info.append(_PCInfo(comp_name, comp_requires_names, comp_description,
                                           cpp_info, comp_aliases))
        return components_info

    def _package_info(self):
        """
        Get the whole package information

        :return: `_PCInfo` object with the package information
        """
        pkg_name = self._get_package_name(self._dep)
        # At first, let's check if we have defined some global requires, e.g., "other::cmp1"
        requires = self._get_cpp_info_requires_names(self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct visible dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [self._get_package_name(req)
                        for req in self._transitive_reqs.values()]
        description = "Conan package: %s" % pkg_name
        aliases = self._get_package_aliases(self._dep)
        cpp_info = self._dep.cpp_info
        return _PCInfo(pkg_name, requires, description, cpp_info, aliases)

    @property
    def pc_files(self):
        """
        Get all the PC files and contents for any dependency:

        * If the given dependency does not have components:
            The PC file will be the dependency one.

        * If the given dependency has components:
            The PC files will be saved in this order:
                1- Package components.
                2- Root component.

            Note: If the root-package PC name matches with any other of the components one, the first one
            is not going to be created. Components have more priority than root package.

        * Apart from those PC files, if there are any aliases declared, they will be created too.
        """
        def _fill_pc_files(pc_info):
            content = self._content_generator.content(pc_info)
            # If no suffix is defined, we can save the *.pc file in the build_context_folder
            if self._is_build_context and self._build_context_folder and not self._suffix:
                # Issue: https://github.com/conan-io/conan/issues/12342
                # Issue: https://github.com/conan-io/conan/issues/14935
                pc_files[f"{self._build_context_folder}/{pc_info.name}.pc"] = content
            else:
                # Saving also the suffixed names as usual
                pc_files[f"{pc_info.name}.pc"] = content

        def _update_pc_files(info):
            _fill_pc_files(info)
            for alias in info.aliases:
                alias_info = _PCInfo(alias, [info.name], f"Alias {alias} for {info.name}", None, [])
                _fill_pc_files(alias_info)

        pc_files = {}
        # If the package has no components, then we have to calculate only the root pc file
        if not self._dep.cpp_info.has_components:
            package_info = self._package_info()
            _update_pc_files(package_info)
            return pc_files

        # First, let's load all the components PC files
        # Loop through all the package's components
        pkg_requires = []
        for component_info in self._components_info():
            _update_pc_files(component_info)
            # Saving components name as the package requires
            pkg_requires.append(component_info.name)

        # Second, let's load the root package's PC file ONLY
        # if it does not already exist in components one
        # Issue related: https://github.com/conan-io/conan/issues/10341
        pkg_name = self._get_package_name(self._dep)
        if f"{pkg_name}.pc" not in pc_files:
            package_info = _PCInfo(pkg_name, pkg_requires, f"Conan package: {pkg_name}",
                                   self._dep.cpp_info, self._get_package_aliases(self._dep))
            _update_pc_files(package_info)
        return pc_files

    @staticmethod
    def _get_name_with_namespace(namespace, name):
        """
        Build a name with a namespace, e.g., openssl-crypto
        """
        return f"{namespace}-{name}"

    @staticmethod
    def _get_package_aliases(dep):
        pkg_aliases = dep.cpp_info.get_property("pkg_config_aliases", check_type=list)
        return pkg_aliases or []

    def _get_component_aliases(self, dep, comp_name):
        if comp_name not in dep.cpp_info.components:
            # foo::foo might be referencing the root cppinfo
            if dep.ref.name == comp_name:
                return self._get_package_aliases(dep)
            raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                 "package requirement".format(name=dep.ref.name,
                                                              cname=comp_name))
        comp_aliases = dep.cpp_info.components[comp_name].get_property("pkg_config_aliases", check_type=list)
        return comp_aliases or []

    def _get_package_name(self, dep):
        pkg_name = dep.cpp_info.get_property("pkg_config_name") or dep.ref.name
        return f"{pkg_name}{self._suffix}"

    def _get_component_name(self, dep, comp_name):
        if comp_name not in dep.cpp_info.components:
            # foo::foo might be referencing the root cppinfo
            if dep.ref.name == comp_name:
                return self._get_package_name(dep)
            raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                 "package requirement".format(name=dep.ref.name,
                                                              cname=comp_name))
        comp_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name")
        return f"{comp_name}{self._suffix}" if comp_name else None


class PkgConfigDeps:

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build *.pc files for the specified libraries
        self.build_context_activated = []
        # If specified, the files/requires/names for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        # DEPRECATED: consumers should use build_context_folder instead
        # FIXME: Conan 3.x: Remove build_context_suffix attribute
        self.build_context_suffix = {}
        # By default, the "[generators_folder]/build" folder will save all the *.pc files activated
        # in the build_context_activated list.
        # Notice that if the `build_context_suffix` attr is defined, the `build_context_folder` one
        # will have no effect.
        # Issue: https://github.com/conan-io/conan/issues/12342
        # Issue: https://github.com/conan-io/conan/issues/14935
        # FIXME: Conan 3.x: build_context_folder should be "build" by default
        self.build_context_folder = None  # Keeping backward-compatibility
        self._properties = {}

    def _validate_build_requires(self, host_req, build_req):
        """
        Check if any package exists at host and build context at the same time, and
        it doesn't have any suffix to avoid any name collisions

        :param host_req: list of host requires
        :param build_req: list of build requires
        """
        activated_br = {r.ref.name for r in build_req.values()
                        if r.ref.name in self.build_context_activated}
        common_names = {r.ref.name for r in host_req.values()}.intersection(activated_br)
        without_suffixes = [common_name for common_name in common_names
                            if not self.build_context_suffix.get(common_name)]
        if without_suffixes:
            raise ConanException(f"The packages {without_suffixes} exist both as 'require' and as"
                                 f" 'build require'. You need to specify a suffix using the "
                                 f"'build_context_suffix' attribute at the PkgConfigDeps generator.")

    @property
    def content(self):
        """
        Get all the .pc files content
        """
        pc_files = {}
        # Get all the dependencies
        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.build  # tool_requires
        test_req = self._conanfile.dependencies.test
        # If self.build_context_suffix is not defined, the build requires will be saved
        # in the self.build_context_folder
        # FIXME: Conan 3.x: Remove build_context_suffix attribute and the validation function
        if self.build_context_folder is None:  # Legacy flow
            if self.build_context_suffix:
                # deprecation warning
                self._conanfile.output.warning("PkgConfigDeps.build_context_suffix attribute has been "
                                               "deprecated. Use PkgConfigDeps.build_context_folder instead.")
            # Check if it exists both as require and as build require without a suffix
            self._validate_build_requires(host_req, build_req)
        elif self.build_context_folder is not None and self.build_context_suffix:
            raise ConanException("It's not allowed to define both PkgConfigDeps.build_context_folder "
                                 "and PkgConfigDeps.build_context_suffix (deprecated).")

        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            # Filter the build_requires not activated with PkgConfigDeps.build_context_activated
            if require.build and dep.ref.name not in self.build_context_activated:
                continue
            for prop, value in self._properties.get(dep.ref.name, {}).items():
                dep.cpp_info.set_property(prop, value)

            # Save all the *.pc files and their contents
            pc_files.update(_PCGenerator(self, require, dep).pc_files)
        return pc_files

    def generate(self):
        """
        Save all the `*.pc` files
        """
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def set_property(self, dep, prop, value):
        """
        Using this method you can overwrite the :ref:`property<PkgConfigDeps Properties>` values set by
        the Conan recipes from the consumer. This can be done for `pkg_config_name`,
        `pkg_config_aliases` and `pkg_config_custom_content` properties.

        :param dep: Name of the dependency to set the :ref:`property<PkgConfigDeps Properties>`. For
         components use the syntax: ``dep_name::component_name``.
        :param prop: Name of the :ref:`property<PkgConfigDeps Properties>`.
        :param value: Value of the property. Use ``None`` to invalidate any value set by the
         upstream recipe.
        """
        self._properties.setdefault(dep, {}).update({prop: value})
