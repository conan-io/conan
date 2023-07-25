"""Makefile generator for Conan dependencies

This generator creates a Makefile (conandeps.mk) with variables for each dependency and consider their components.
To simplify its usage, it also creates global variables with aggregated values from all dependencies.
This generator does not work like a toolchain, it does not include settings.

For better customization, it allows appending prefixes as flags variables:

- CONAN_LIB_FLAG: Add a prefix to all libs variables, e.g. -l
- CONAN_DEFINE_FLAG: Add a prefix to all defines variables, e.g. -D
- CONAN_SYSTEM_LIB_FLAG: Add a prefix to all system_libs variables, e.g. -l
- CONAN_INCLUDE_DIR_FLAG: Add a prefix to all include dirs variables, e.g. -I
- CONAN_LIB_DIR_FLAG: Add a prefix to all lib dirs variables, e.g. -L


The conandeps.mk file layout is as follows:

- CONAN_DEPS: list all transitive and intransitive dependencies names without version (e.g. zlib)
- Iterate over each dependency and its components:
    - Prints name, version, root folder, regular folders, libs and flags
    - Components are rootified to avoid repeating same prefix twice for the root folder
    - Components libs, folder and flags are solved as variables to avoid repeating same name twice
- Aggregated global variables for simplification, sum all dependencies to common variables (e.g. CONAN_INCLUDE_DIRS)

"""

import os
import re
import textwrap

from jinja2 import Template, StrictUndefined

from conan.internal import check_duplicated_generator
from conan.tools.files import save


CONAN_MAKEFILE_FILENAME = "conandeps.mk"


def _get_formatted_dirs(folders: list, prefix_path_: str, name: str) -> list:
    """ Format the directories to be used in the makefile, adding the prefix path if needed
    :param folders: list of directories
    :param prefix_path_: prefix path
    :param name: component name
    :return: list of formatted directories
    """
    ret = []
    for i, directory in enumerate(folders):
        directory = os.path.normpath(directory).replace("\\", "/")
        prefix = ""
        if not os.path.isabs(directory):
            prefix = f"$(CONAN_ROOT_{name})/"
        elif directory.startswith(prefix_path_):
            prefix = f"$(CONAN_ROOT_{name})/"
            directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
        ret.append(f"{prefix}{directory}")
    return ret


def _makefy(name: str) -> str:
    """
    Convert a name to Make-variable-friendly syntax
    """
    return re.sub(r'[^0-9A-Z_]', '_', name.upper())


def _conan_prefix_flag(variable: str) -> str:
    """
    Return a global flag to be used as prefix to any value in the makefile
    """
    return f"$(CONAN_{variable.upper()}_FLAG)" if variable else ""


def _common_cppinfo_variables() -> dict:
    """
    Regular cppinfo variables exported by any Conanfile and their Makefile prefixes
    """
    return {
        "objects": None,
        "libs": "lib",
        "defines": "define",
        "cflags": None,
        "cxxflags": None,
        "sharedlinkflags": None,
        "exelinkflags": None,
        "frameworks": None,
        "requires": None,
        "system_libs": "system_lib",
    }


def _common_cppinfo_dirs() -> dict:
    """
    Regular cppinfo folders exported by any Conanfile and their Makefile prefixes
    """
    return {
        'includedirs': "include_dir",
        'libdirs': "lib_dir",
        'bindirs': None,
        'srcdirs': None,
        'builddirs': None,
        'resdirs': None,
        'frameworkdirs': None,
    }


class MakeInfo:
    """
    Store temporary information about each dependency
    """
    def __init__(self, name: str, dirs: list, flags: list):
        self.name = name
        self.dirs = dirs
        self.flags = flags


class GlobalContentGenerator:
    """
    Generates the formatted content for global variables (e.g. CONAN_DEPS, CONAN_LIBS)
    """

    template = textwrap.dedent("""\
            {%- macro format_map_values(values) -%}
            {%- for var, value in values.items() -%}
            {%- if value|length > 0 -%}
            CONAN_{{ var.upper() }} = {{ format_list_values(value) }}
            {%- endif -%}
            {%- endfor -%}
            {%- endmacro -%}

            {%- macro format_list_values(values) -%}
            {% if values|length == 1 %}
            {{ values[0] }}

            {% elif values|length > 1 %}
            \\
            {% for value in values[:-1] %}
            \t{{ value }} \\
            {% endfor %}
            \t{{ values|last }}

            {% endif %}
            {%- endmacro %}

            # Aggregated global variables


            {{ format_map_values(dirs) -}}
            {{- format_map_values(flags) -}}
            """)

    template_deps = textwrap.dedent("""\
            {%- macro format_list_values(values) -%}
            {% if values|length == 1 %}
            {{ values[0] }}

            {% elif values|length > 1 %}
            \\
            {% for value in values[:-1] %}
            \t{{ value }} \\
            {% endfor %}
            \t{{ values|last }}

            {% endif %}
            {%- endmacro -%}

            CONAN_DEPS = {{ format_list_values(deps) }}
            """)

    def __init__(self, conanfile):
        self._conanfile = conanfile

    def content(self, deps_cpp_info_dirs: list, deps_cpp_info_flags: list) -> str:
        """
        Generate content for Cppinfo variables (e.g. CONAN_LIBS, CONAN_INCLUDE_DIRS)
        :param deps_cpp_info_dirs: Formatted dependencies folders
        :param deps_cpp_info_flags: Formatted dependencies variables
        """
        context = {"dirs": deps_cpp_info_dirs, "flags": deps_cpp_info_flags}
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)

    def deps_content(self, dependencies_names: list) -> str:
        """
        Generate content for CONAN_DEPS (e.g. CONAN_DEPS = zlib, openssl)
        :param dependencies_names: Non-formatted dependencies names
        """
        context = {"deps": dependencies_names}
        template = Template(self.template_deps, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)


class GlobalGenerator:
    """
    Process all collected dependencies and parse to generate global content
    """

    def __init__(self, conanfile, make_infos):
        self._conanfile = conanfile
        self._make_infos = make_infos

    def _get_dependency_dirs(self) -> list:
        """
        List regular directories from cpp_info and format them to be used in the makefile
        """
        dirs = {}
        for var in _common_cppinfo_dirs():
            key = var.replace("dirs", "_dirs")
            dirs[key] = [f"$(CONAN_{key.upper()}_{_makefy(makeinfo.name)})" for makeinfo in self._make_infos if var in makeinfo.dirs]
        return dirs

    def _get_dependency_flags(self) -> list:
        """
        List common variables from cpp_info and format them to be used in the makefile
        """
        flags = {}
        for var in _common_cppinfo_variables().keys():
            key = var.replace("dirs", "_dirs")
            flags[key] = [f"$(CONAN_{key.upper()}_{_makefy(makeinfo.name)})" for makeinfo in self._make_infos if var in makeinfo.flags]
        return flags

    def generate(self) -> str:
        """
        Process folder and variables for a dependency and generates its Makefile content
        """
        glob_content_gen = GlobalContentGenerator(self._conanfile)
        dirs = self._get_dependency_dirs()
        flags = self._get_dependency_flags()
        return glob_content_gen.content(dirs, flags)

    def deps_generate(self) -> str:
        """
        Process dependencies names and generates its Makefile content.
        It should be added as first variable in the Makefile.
        """
        dependencies = [makeinfo.name for makeinfo in self._make_infos if makeinfo.name != self._conanfile.name]
        glob_content_gen = GlobalContentGenerator(self._conanfile)
        return glob_content_gen.deps_content(dependencies)


class DepComponentContentGenerator:
    """
    Generates Makefile content for each dependency component
    """

    template = textwrap.dedent("""\
        {%- macro format_map_values(values) -%}
        {%- for var, value in values.items() -%}
        CONAN_{{ var.upper() }}_{{ dep_name }}_{{ name }} = {{ format_list_values(value) }}
        {%- endfor -%}
        {%- endmacro -%}

        {%- macro format_list_values(values) -%}
        {% if values|length == 1 %}
        {{ values[0] }}

        {% elif values|length > 1 %}
        \\
        {% for value in values[:-1] %}
        \t{{ value }} \\
        {% endfor %}
        \t{{ values|last }}

        {% endif %}
        {%- endmacro -%}

        # {{ dep.ref.name }}::{{ comp_name }}

        {{ format_map_values(dirs) -}}
        {{- format_map_values(flags) -}}
        """)

    def __init__(self, conanfile: object, dependency: object, component_name: str, root: str, dirs: dict, flags: dict):
        self._conanfile = conanfile
        self._dep = dependency
        self._name = component_name
        self._root = root
        self._dirs = dirs or {}
        self._flags = flags or {}

    def content(self) -> str:
        """
        Format template and generate Makefile component
        """
        context = {
            "dep": self._dep,
            "comp_name": self._name,
            "dep_name": _makefy(self._dep.ref.name),
            "name": _makefy(self._name),
            "root": self._root,
            "dirs": self._dirs,
            "flags": self._flags
        }
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)


class DepContentGenerator:
    """
    Generates Makefile content for a dependency
    """

    template = textwrap.dedent("""\
        {%- macro format_map_values(values) -%}
        {%- for var, value in values.items() -%}
        CONAN_{{ var.upper() }}_{{ name }} = {{ format_list_values(value) }}
        {%- endfor -%}
        {%- endmacro -%}

        {%- macro format_list_values(values) -%}
        {% if values|length == 1 %}
        {{ values[0] }}

        {% elif values|length > 1 %}
        \\
        {% for value in values[:-1] %}
        \t{{ value }} \\
        {% endfor %}
        \t{{ values|last }}

        {% endif %}
        {%- endmacro %}

        # {{ dep.ref.name }}/{{ dep.ref.version }}


        CONAN_NAME_{{ name }} = {{ dep.ref.name }}

        CONAN_VERSION_{{ name }} = {{ dep.ref.version }}

        CONAN_ROOT_{{ name }} = {{ root }}

        {% if sysroot|length > 0 %}
        CONAN_SYSROOT_{{ name }} = {{ format_list_values(sysroot) }}
        {% endif %}
        {{- format_map_values(dirs) }}
        {{- format_map_values(flags) -}}
        {%- if components|length > 0 -%}
        CONAN_COMPONENTS_{{ name }} = {{ format_list_values(components) }}
        {%- endif -%}
        """)

    def __init__(self, conanfile: object, dependency: object, root: str, sysroot: str, dirs: dict, flags: dict):
        self._conanfile = conanfile
        self._dep = dependency
        self._root = root
        self._sysroot = sysroot
        self._dirs = dirs or {}
        self._flags = flags or {}

    def content(self) -> str:
        """
        Parse dependency variables and generate its Makefile content
        """
        context = {
            "dep": self._dep,
            "name": _makefy(self._dep.ref.name),
            "root": self._root,
            "sysroot": self._sysroot,
            "dirs": self._dirs,
            "flags": self._flags,
            "components": list(self._dep.cpp_info.get_sorted_components().keys())
        }
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)


class DepComponentGenerator:

    def __init__(self, conanfile: object, dependency: object, makeinfo: MakeInfo, component_name: str, component: object, root: str):
        self._conanfile = conanfile
        self._dep = dependency
        self._name = component_name
        self._comp = component
        self._root = root
        self._makeinfo = makeinfo

    def _get_component_dirs(self) -> dict:
        """
        List regular directories from cpp_info and format them to be used in the makefile
        """
        dirs = {}
        for var, flag in _common_cppinfo_dirs().items():
            cppinfo_value = getattr(self._comp, var)
            formatted_dirs = _get_formatted_dirs(cppinfo_value, self._root, _makefy(self._name))
            if formatted_dirs:
                self._makeinfo.dirs.append(var)
                var = var.replace("dirs", "_dirs")
                formatted_dirs = self._rootify(self._root, self._dep.ref.name, cppinfo_value)
                dirs[var] = [_conan_prefix_flag(flag) + it for it in formatted_dirs]
        return dirs

    def _rootify(self, root: str, root_id: str, path_list: list) -> list:
        """
        Replaces component folder path by its root node folder path in case they match
        :param root: root folder path for component's father
        :param root_id: component's dependency name
        :param path_list: folder list available in the component
        :return: A formatted folder list, solving root folder path as prefix
        """
        root_len = len(root)
        root_with_sep = root + os.sep
        root_var_ref = f"$(CONAN_ROOT_{_makefy(root_id)})"
        return [root_var_ref + path[root_len:].replace("\\", "/") if path.startswith(root_with_sep) else path for path in path_list]

    def _get_component_flags(self) -> dict:
        """
        List common variables from cpp_info and format them to be used in the makefile
        """
        flags = {}
        for var, prefix_var in _common_cppinfo_variables().items():
            cppinfo_value = getattr(self._comp, var)
            if not cppinfo_value:
                continue
            if "flags" in var:
                cppinfo_value = [var.replace('"', '\\"') for var in cppinfo_value]
            if cppinfo_value:
                flags[var.upper()] = [_conan_prefix_flag(prefix_var) + it for it in cppinfo_value]
                self._makeinfo.flags.append(var)
        return flags

    def generate(self) -> str:
        """
        Process component cpp_info variables and generate its Makefile content
        """
        dirs = self._get_component_dirs()
        flags = self._get_component_flags()
        comp_content_gen = DepComponentContentGenerator(self._conanfile, self._dep, self._name, self._root, dirs, flags)
        comp_content = comp_content_gen.content()
        return comp_content


class DepGenerator:
    """
    Process a dependency cpp_info variables and generate its Makefile content
    """

    def __init__(self, conanfile: object, dependency: object):
        self._conanfile = conanfile
        self._dep = dependency
        self._info = MakeInfo(self._dep.ref.name, [], [])

    def make_global_info(self) -> MakeInfo:
        """
        Remove duplicated folders and flags from current MakeInfo
        :return: Dependency folder and flags
        """
        self._info.dirs = list(set(self._info.dirs))
        self._info.flags = list(set(self._info.flags))
        return self._info

    def _get_dependency_dirs(self, root: str, dependency: object) -> dict:
        """
        List regular directories from cpp_info and format them to be used in the makefile
        :param root: Package root folder
        :param dep: Dependency object
        :return: A dictionary with regular folder name and its formatted path
        """
        dirs = {}
        for var, prefix in _common_cppinfo_dirs().items():
            cppinfo_value = getattr(dependency.cpp_info, var)
            formatted_dirs = _get_formatted_dirs(cppinfo_value, root, _makefy(dependency.ref.name))
            if formatted_dirs:
                self._info.dirs.append(var)
                var = var.replace("dirs", "_dirs")
                dirs[var] = [_conan_prefix_flag(prefix) + it for it in formatted_dirs]
        return dirs

    def _get_dependency_flags(self, dependency: object) -> dict:
        """
        List common variables from cpp_info and format them to be used in the makefile
        :param dep: Dependency object
        """
        flags = {}
        for var, prefix_var in _common_cppinfo_variables().items():
            cppinfo_value = getattr(dependency.cpp_info, var)
            # Use component cpp_info info when does not provide any value
            if not cppinfo_value and hasattr(dependency.cpp_info, "components"):
                cppinfo_value = [f"$(CONAN_{var.upper()}_{_makefy(dependency.ref.name)}_{_makefy(name)})" for name, obj in dependency.cpp_info.components.items() if getattr(obj, var.lower())]
                # avoid repeating same prefix twice
                prefix_var = ""
            if "flags" in var:
                cppinfo_value = [var.replace('"', '\\"') for var in cppinfo_value]
            if cppinfo_value:
                self._info.flags.append(var)
                flags[var.upper()] = [_conan_prefix_flag(prefix_var) + it for it in cppinfo_value]
        return flags

    def _get_sysroot(self, root: str) -> list:
        """
        Get the sysroot of the dependency. Sysroot is a list of directories, or a single directory
        """
        sysroot = self._dep.cpp_info.sysroot if isinstance(self._dep.cpp_info.sysroot, list) else [self._dep.cpp_info.sysroot]
        # sysroot may return ['']
        if not sysroot or not sysroot[0]:
            return []
        return _get_formatted_dirs(sysroot, root, _makefy(self._dep.ref.name)) if sysroot and sysroot[0] else None

    def _get_root_folder(self):
        """
        Get the root folder of the dependency
        """
        root = self._dep.recipe_folder if self._dep.package_folder is None else self._dep.package_folder
        return root.replace("\\", "/")

    def generate(self) -> str:
        """
        Process dependency folders and flags to generate its Makefile content. Plus, execute same
        steps for each component
        """
        root = self._get_root_folder()
        sysroot = self._get_sysroot(root)
        dirs = self._get_dependency_dirs(root, self._dep)
        flags = self._get_dependency_flags(self._dep)
        dep_content_gen = DepContentGenerator(self._conanfile, self._dep, root, sysroot, dirs, flags)
        content = dep_content_gen.content()

        for comp_name, comp in self._dep.cpp_info.get_sorted_components().items():
            component_gen = DepComponentGenerator(self._conanfile, self._dep, self._info, comp_name, comp, root)
            content += component_gen.generate()

        return content


class MakeDeps(object):
    """
    Generates a Makefile with the variables needed to build a project with the specified.
    """

    _title = "# This Makefile has been generated by Conan. DO NOT EDIT!\n"

    def __init__(self, conanfile: object):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

    def generate(self) -> None:
        """
        Parse a ConanFile object, collecting all dependencies and components, then, generating a Makefile
        """
        check_duplicated_generator(self, self._conanfile)

        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.build  # tool_requires
        test_req = self._conanfile.dependencies.test

        content_buffer = f"{self._title}\n"
        deps_buffer = ""

        # Filter the build_requires not activated for any requirement
        dependencies = [tup for tup in list(host_req.items()) + list(build_req.items()) + list(test_req.items()) if not tup[0].build]

        make_infos = []

        for require, dep in dependencies:
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0
            if require.build:
                continue

            dep_gen = DepGenerator(self._conanfile, dep)
            make_infos.append(dep_gen.make_global_info())
            deps_buffer += dep_gen.generate()

        glob_gen = GlobalGenerator(self._conanfile, make_infos)
        content_buffer += glob_gen.deps_generate() + deps_buffer + glob_gen.generate()

        save(self._conanfile, CONAN_MAKEFILE_FILENAME, content_buffer)
        self._conanfile.output.info(f"Generated {CONAN_MAKEFILE_FILENAME}")
