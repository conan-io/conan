import os
import textwrap
from collections import namedtuple

from jinja2 import Template, StrictUndefined

from conan.internal import check_duplicated_generator
from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.errors import ConanException
from conans.util.files import save


def _get_name_with_namespace(namespace, name):
    """
    Build a name with a namespace, e.g., openssl-crypto
    """
    return f"{namespace}-{name}"


def _get_package_reference_name(dep):
    """
    Get the reference name for the given package
    """
    return dep.ref.name


def _get_package_aliases(dep):
    pkg_aliases = dep.cpp_info.get_property("pkg_config_aliases")
    return pkg_aliases or []


def _get_component_aliases(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_name:
            return _get_package_aliases(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_aliases = dep.cpp_info.components[comp_name].get_property("pkg_config_aliases")
    return comp_aliases or []


def _get_package_name(dep, build_context_suffix=None):
    pkg_name = dep.cpp_info.get_property("pkg_config_name") or _get_package_reference_name(dep)
    suffix = _get_suffix(dep, build_context_suffix)
    return f"{pkg_name}{suffix}"


def _get_component_name(dep, comp_name, build_context_suffix=None):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_name:
            return _get_package_name(dep, build_context_suffix)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name")
    suffix = _get_suffix(dep, build_context_suffix)
    return f"{comp_name}{suffix}" if comp_name else None


def _get_suffix(req, build_context_suffix=None):
    """
    Get the package name suffix coming from PkgConfigDeps.build_context_suffix attribute, but only
    for requirements declared as build requirement.

    :param req: requirement ConanFile instance
    :param build_context_suffix: `dict` with all the suffixes
    :return: `str` with the suffix
    """
    if not build_context_suffix or not req.is_build_context:
        return ""
    return build_context_suffix.get(req.ref.name, "")


def _get_formatted_dirs(folders, prefix_path_):
    ret = []
    for i, directory in enumerate(folders):
        directory = os.path.normpath(directory).replace("\\", "/")
        prefix = ""
        if not os.path.isabs(directory):
            prefix = "${prefix}/"
        elif directory.startswith(prefix_path_):
            prefix = "${prefix}/"
            directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
        ret.append("%s%s" % (prefix, directory))
    return ret


_PCInfo = namedtuple("PCInfo", ['name', 'requires', 'description', 'cpp_info', 'aliases'])


class _PCContentGenerator:

    template = textwrap.dedent("""\
        {%- macro get_libs(libdirs, cpp_info, gnudeps_flags) -%}
        {%- for _ in libdirs -%}
        {{ '-L"${libdir%s}"' % loop.index + " " }}
        {%- endfor -%}
        {%- for sys_lib in (cpp_info.libs + cpp_info.system_libs) -%}
        {{ "-l%s" % sys_lib + " " }}
        {%- endfor -%}
        {%- for shared_flag in (cpp_info.sharedlinkflags + cpp_info.exelinkflags) -%}
        {{  shared_flag + " " }}
        {%- endfor -%}
        {%- for framework in (gnudeps_flags.frameworks + gnudeps_flags.framework_paths) -%}
        {{ framework + " " }}
        {%- endfor -%}
        {%- endmacro -%}

        {%- macro get_cflags(includedirs, cxxflags, cflags, defines) -%}
        {%- for _ in includedirs -%}
        {{ '-I"${includedir%s}"' % loop.index + " " }}
        {%- endfor -%}
        {%- for cxxflag in cxxflags -%}
        {{ cxxflag + " " }}
        {%- endfor -%}
        {%- for cflag in cflags-%}
        {{ cflag + " " }}
        {%- endfor -%}
        {%- for define in defines-%}
        {{  "-D%s" % define + " " }}
        {%- endfor -%}
        {%- endmacro -%}

        prefix={{ prefix_path }}
        {% for path in libdirs %}
        {{ "libdir{}={}".format(loop.index, path) }}
        {% endfor %}
        {% for path in includedirs %}
        {{ "includedir%d=%s" % (loop.index, path) }}
        {% endfor %}
        {% if pkg_config_custom_content %}
        # Custom PC content
        {{ pkg_config_custom_content }}
        {% endif %}

        Name: {{ name }}
        Description: {{ description }}
        Version: {{ version }}
        Libs: {{ get_libs(libdirs, cpp_info, gnudeps_flags) }}
        Cflags: {{ get_cflags(includedirs, cxxflags, cflags, defines) }}
        {% if requires|length %}
        Requires: {{ requires|join(' ') }}
        {% endif %}
    """)

    shortened_template = textwrap.dedent("""\
        Name: {{ name }}
        Description: {{ description }}
        Version: {{ version }}
        {% if requires|length %}
        Requires: {{ requires|join(' ') }}
        {% endif %}
    """)

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep

    def content(self, info):
        assert isinstance(info, _PCInfo) and info.cpp_info is not None

        # If editable, package_folder can be None
        root_folder = self._dep.recipe_folder if self._dep.package_folder is None \
            else self._dep.package_folder
        version = info.cpp_info.get_property("component_version") or self._dep.ref.version

        prefix_path = root_folder.replace("\\", "/")
        libdirs = _get_formatted_dirs(info.cpp_info.libdirs, prefix_path)
        includedirs = _get_formatted_dirs(info.cpp_info.includedirs, prefix_path)
        custom_content = info.cpp_info.get_property("pkg_config_custom_content")

        context = {
            "prefix_path": prefix_path,
            "libdirs": libdirs,
            "includedirs": includedirs,
            "pkg_config_custom_content": custom_content,
            "name": info.name,
            "description": info.description,
            "version": version,
            "requires": info.requires,
            "cpp_info": info.cpp_info,
            "cxxflags": [var.replace('"', '\\"') for var in info.cpp_info.cxxflags],
            "cflags": [var.replace('"', '\\"') for var in info.cpp_info.cflags],
            "defines": [var.replace('"', '\\"') for var in info.cpp_info.defines],
            "gnudeps_flags": GnuDepsFlags(self._conanfile, info.cpp_info)
        }
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return template.render(context)

    def shortened_content(self, info):
        assert isinstance(info, _PCInfo)

        context = {
            "name": info.name,
            "description": info.description,
            "version": self._dep.ref.version,
            "requires": info.requires
        }
        template = Template(self.shortened_template, trim_blocks=True,
                            lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)


class _PCGenerator:

    def __init__(self, conanfile, dep, build_context_suffix=None):
        self._conanfile = conanfile
        self._build_context_suffix = build_context_suffix or {}
        self._dep = dep
        self._content_generator = _PCContentGenerator(self._conanfile, self._dep)

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
        ```
        Or:

        ```python
        from conan import ConanFile
        class PkgConfigConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.components["cmp"].requires = ["other::cmp1"]
        ```
        """
        dep_ref_name = _get_package_reference_name(self._dep)
        ret = []
        for req in cpp_info.requires:
            pkg_ref_name, comp_ref_name = req.split("::") if "::" in req else (dep_ref_name, req)
            # For instance, dep == "hello/1.0" and req == "other::cmp1" -> hello != other
            if dep_ref_name != pkg_ref_name:
                req_conanfile = self._dep.dependencies.host[pkg_ref_name]
            else:  # For instance, dep == "hello/1.0" and req == "hello::cmp1" -> hello == hello
                req_conanfile = self._dep
            comp_name = _get_component_name(req_conanfile, comp_ref_name, self._build_context_suffix)
            if not comp_name:
                pkg_name = _get_package_name(req_conanfile, self._build_context_suffix)
                # Creating a component name with namespace, e.g., dep-comp1
                comp_name = _get_name_with_namespace(pkg_name, comp_ref_name)
            ret.append(comp_name)
        return ret

    @property
    def components_info(self):
        """
        Get the whole package and its components information like their own requires, names and even
        the cpp_info for each component.

        :return: `list` of `_PCInfo` objects with all the components information
        """
        pkg_name = _get_package_name(self._dep, self._build_context_suffix)
        components_info = []
        # Loop through all the package's components
        for comp_ref_name, cpp_info in self._dep.cpp_info.get_sorted_components().items():
            # At first, let's check if we have defined some components requires, e.g., "dep::cmp1"
            comp_requires_names = self._get_cpp_info_requires_names(cpp_info)
            comp_name = _get_component_name(self._dep, comp_ref_name, self._build_context_suffix)
            if not comp_name:
                comp_name = _get_name_with_namespace(pkg_name, comp_ref_name)
                comp_description = f"Conan component: {comp_name}"
            else:
                comp_description = f"Conan component: {pkg_name}-{comp_name}"
            comp_aliases = _get_component_aliases(self._dep, comp_ref_name)
            # Save each component information
            components_info.append(_PCInfo(comp_name, comp_requires_names, comp_description,
                                           cpp_info, comp_aliases))
        return components_info

    @property
    def package_info(self):
        """
        Get the whole package information

        :return: `_PCInfo` object with the package information
        """
        pkg_name = _get_package_name(self._dep, self._build_context_suffix)
        # At first, let's check if we have defined some global requires, e.g., "other::cmp1"
        requires = self._get_cpp_info_requires_names(self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [_get_package_name(req, self._build_context_suffix)
                        for req in self._dep.dependencies.direct_host.values()]
        description = "Conan package: %s" % pkg_name
        aliases = _get_package_aliases(self._dep)
        cpp_info = self._dep.cpp_info
        return _PCInfo(pkg_name, requires, description, cpp_info, aliases)

    @property
    def pc_files(self):
        """
        Get all the PC files and contents for any dependency:

        * If the given dependency does not have components:
            The PC file will be the depency one.

        * If the given dependency has components:
            The PC files will be saved in this order:
                1- Package components.
                2- Root component.

            Note: If the root-package PC name matches with any other of the components one, the first one
            is not going to be created. Components have more priority than root package.

        * Apart from those PC files, if there are any aliases declared, they will be created too.
        """
        def _update_pc_files(info):
            pc_files[f"{info.name}.pc"] = self._content_generator.content(info)
            for alias in info.aliases:
                alias_info = _PCInfo(alias, [info.name], f"Alias {alias} for {info.name}", None, [])
                pc_files[f"{alias}.pc"] = self._content_generator.shortened_content(alias_info)

        pc_files = {}
        # If the package has no components, then we have to calculate only the root pc file
        if not self._dep.cpp_info.has_components:
            package_info = self.package_info
            _update_pc_files(package_info)
            return pc_files

        # First, let's load all the components PC files
        # Loop through all the package's components
        pkg_requires = []
        for component_info in self.components_info:
            _update_pc_files(component_info)
            # Saving components name as the package requires
            pkg_requires.append(component_info.name)

        # Second, let's load the root package's PC file ONLY
        # if it does not already exist in components one
        # Issue related: https://github.com/conan-io/conan/issues/10341
        pkg_name = _get_package_name(self._dep, self._build_context_suffix)
        if f"{pkg_name}.pc" not in pc_files:
            package_info = _PCInfo(pkg_name, pkg_requires, f"Conan package: {pkg_name}", None,
                                   _get_package_aliases(self._dep))
            # It'll be enough creating a shortened PC file. This file will be like an alias
            pc_files[f"{package_info.name}.pc"] = self._content_generator.shortened_content(package_info)
            for alias in package_info.aliases:
                alias_info = _PCInfo(alias, [package_info.name],
                                     f"Alias {alias} for {package_info.name}", None, [])
                pc_files[f"{alias}.pc"] = self._content_generator.shortened_content(alias_info)

        return pc_files


class PkgConfigDeps:

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build *.pc files for the specified libraries
        self.build_context_activated = []
        # If specified, the files/requires/names for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        self.build_context_suffix = {}

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
                            if self.build_context_suffix.get(common_name) is None]
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

        # Check if it exists both as require and as build require without a suffix
        self._validate_build_requires(host_req, build_req)

        for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0
            # Filter the build_requires not activated with PkgConfigDeps.build_context_activated
            if require.build and dep.ref.name not in self.build_context_activated:
                continue

            pc_generator = _PCGenerator(self._conanfile, dep, build_context_suffix=self.build_context_suffix)
            pc_files.update(pc_generator.pc_files)
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
