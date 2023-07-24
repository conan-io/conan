import os
import re
import textwrap
from dataclasses import dataclass

from jinja2 import Template, StrictUndefined

from conan.internal import check_duplicated_generator
from conan.tools.files import save


CONAN_MAKEFILE_FILENAME = "conandeps.mk"


def _get_formatted_dirs(folders, prefix_path_, name):
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


def _makefy(name):
    """
    Convert a name to Make-variable-friendly syntax
    """
    return re.sub(r'[^0-9A-Z_]', '_', name.upper())


@dataclass
class MakeInfo:
    name: str
    dirs: list
    flags: list


class GlobalContentGenerator:
    template = textwrap.dedent("""\
            {%- macro format_map_values(values) -%}
            {%- for var, value in values.items() -%}
            {% if value|length > 0 %}
            CONAN_{{ var.upper() }} = {{ format_list_values(value) }}
            {% endif %}
            {%- endfor -%}
            {%- endmacro -%}

            {%- macro format_list_values(values) -%}
            {% if values|length == 1 %}
            {{ values[0] }}

            {% else %}
            \\
            {% for value in values[:-1] %}
            \t{{ value }} \\
            {% endfor %}
            \t{{ values|last }}

            {% endif %}
            {%- endmacro -%}

            # Aggregated global variables

            {{ format_map_values(dirs) }}
            {{- format_map_values(flags) -}}
            """)

    template_deps = textwrap.dedent("""\
            {%- macro format_list_values(values) -%}
            {% if values|length == 1 %}
            {{ values[0] }}

            {% else %}
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

    def content(self, deps_cpp_info_dirs, deps_cpp_info_flags):
        context = {"dirs": deps_cpp_info_dirs, "flags": deps_cpp_info_flags}
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)

    def deps_content(self, dependencies_names):
        context = {"deps": dependencies_names}
        template = Template(self.template_deps, trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
        return template.render(context)


class GlobalGenerator:

    def __init__(self, conanfile, make_infos):
        self._conanfile = conanfile
        self._make_infos = make_infos

    def _get_dependency_dirs(self):
        """
        List regular directories from cpp_info and format them to be used in the makefile
        :param dep: Dependency list to add to the global list
        """
        dirs = {}
        for var in ['includedirs', 'libdirs', 'bindirs', 'srcdirs', 'builddirs', 'resdirs', 'frameworkdirs']:
            key = var.replace("dirs", "_dirs")
            dirs[key] = [f"$(CONAN_{key.upper()}_{_makefy(makeinfo.name)})" for makeinfo in self._make_infos if var in makeinfo.dirs]
        return dirs

    def _get_dependency_flags(self):
        """
        List common variables from cpp_info and format them to be used in the makefile
        :param dep: Dependency object
        """
        common_variables = {
            "objects": None,
            "libs": "lib",
            "system_libs": "system_lib",
            "defines": "define",
            "cflags": None,
            "cxxflags": None,
            "sharedlinkflags": None,
            "exelinkflags": None,
            "frameworks": None,
            "requires": None,
        }
        flags = {}
        for var in common_variables.keys():
            key = var.replace("dirs", "_dirs")
            flags[key] = [f"$(CONAN_{key.upper()}_{_makefy(makeinfo.name)})" for makeinfo in self._make_infos if var in makeinfo.flags]
        return flags

    def generate(self):
        glob_content_gen = GlobalContentGenerator(self._conanfile)
        dirs = self._get_dependency_dirs()
        flags = self._get_dependency_flags()
        return glob_content_gen.content(dirs, flags)

    def deps_generate(self):
        dependencies = [makeinfo.name for makeinfo in self._make_infos if makeinfo.name != self._conanfile.name]
        glob_content_gen = GlobalContentGenerator(self._conanfile)
        return glob_content_gen.deps_content(dependencies)


class DepComponentContentGenerator:
    template = textwrap.dedent("""\
        {%- macro format_map_values(values) -%}
        {%- for var, value in values.items() -%}
        CONAN_{{ var.upper() }}_{{ dep_name }}_{{ name }} = {{ format_list_values(value) }}
        {%- endfor -%}
        {%- endmacro -%}

        {%- macro format_list_values(values) -%}
        {% if values|length == 1 %}
        {{ values[0] }}

        {% else %}
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

    def __init__(self, conanfile, dependency, component_name, component, root, dirs=None, flags=None):
        self._conanfile = conanfile
        self._dep = dependency
        self._name = component_name
        self._comp = component
        self._root = root
        self._dirs = dirs or {}
        self._flags = flags or {}

    def _conan_prefix_flag(self, variable):
        """
        Return a global flag to be used as prefix to any value in the makefile
        """
        return f"$(CONAN_{variable.upper()}_FLAG)" if variable else ""

    def content(self):
        context = {
            "dep": self._dep,
            "comp": self._comp,
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
    template = textwrap.dedent("""\
        {%- macro format_map_values(values) -%}
        {%- for var, value in values.items() -%}
        CONAN_{{ var.upper() }}_{{ name }} = {{ format_list_values(value) }}
        {%- endfor -%}
        {%- endmacro -%}

        {%- macro format_list_values(values) -%}
        {% if values|length == 1 %}
        {{ values[0] }}

        {% else %}
        \\
        {% for value in values[:-1] %}
        \t{{ value }} \\
        {% endfor %}
        \t{{ values|last }}

        {% endif %}
        {%- endmacro -%}

        # {{ dep.ref.name }}/{{ dep.ref.version }}

        CONAN_NAME_{{ name }} = {{ dep.ref.name }}

        CONAN_VERSION_{{ name }} = {{ dep.ref.version }}

        CONAN_ROOT_{{ name }} = {{ root }}

        {% if sysroot %}
        CONAN_SYSROOT_{{ name }} = {{ sysroot }}
        {% endif %}
        {{- format_map_values(dirs) }}
        {{- format_map_values(flags) -}}
        {%- if components|length > 0 -%}
        CONAN_COMPONENTS_{{ name }} = {{ format_list_values(components) }}
        {%- endif -%}
        """)

    def __init__(self, conanfile, dependency, root, sysroot=None, dirs=None, flags=None):
        self._conanfile = conanfile
        self._dep = dependency
        self._root = root
        self._sysroot = sysroot
        self._dirs = dirs or {}
        self._flags = flags or {}

    def _conan_prefix_flag(self, variable):
        """
        Return a global flag to be used as prefix to any value in the makefile
        """
        return f"$(CONAN_{variable.upper()}_FLAG)" if variable else ""

    def content(self):
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

    def __init__(self, conanfile, dependency, makeinfo, component_name, component, root):
        self._conanfile = conanfile
        self._dep = dependency
        self._name = component_name
        self._comp = component
        self._root = root
        self._makeinfo = makeinfo

    def _conan_prefix_flag(self, variable):
        """
        Return a global flag to be used as prefix to any value in the makefile
        """
        return f"$(CONAN_{variable.upper()}_FLAG)" if variable else ""

    def _get_component_dirs(self):
        """
        List regular directories from cpp_info and format them to be used in the makefile
        :param root: Package root folder
        :param dep: Dependency object
        """
        dirs = {}
        for var in ['includedirs', 'libdirs', 'bindirs', 'srcdirs', 'builddirs', 'resdirs', 'frameworkdirs']:
            cppinfo_value = getattr(self._comp, var)
            formatted_dirs = _get_formatted_dirs(cppinfo_value, self._root, _makefy(self._name))
            if formatted_dirs:
                self._makeinfo.dirs.append(var)
                var = var.replace("dirs", "_dirs")
                formatted_dirs = self._rootify(self._root, self._dep.ref.name, formatted_dirs)
                dirs[var] = [self._conan_prefix_flag(var) + it for it in formatted_dirs]
        return dirs

    def _rootify(self, root, root_id, path_list):
        root_len = len(root)
        root_with_sep = root + os.path.sep
        root_var_ref = f"$(CONAN_ROOT_{_makefy(root_id)})"
        return [root_var_ref + path[root_len:] if path.startswith(root_with_sep) else path for path in path_list]

    def _get_component_flags(self):
        """
        List common variables from cpp_info and format them to be used in the makefile
        :param dep: Dependency object
        """
        common_variables = {
            "objects": "",
            "libs": "lib",
            "system_libs": "system_lib",
            "defines": "define",
            "cflags": "",
            "cxxflags": "",
            "sharedlinkflags": "",
            "exelinkflags": "",
            "frameworks": "",
            "requires": "",
        }
        flags = {}
        for var, prefix_var in common_variables.items():
            cppinfo_value = getattr(self._comp, var)
            if not cppinfo_value:
                continue
            if "flags" in var:
                cppinfo_value = [var.replace('"', '\\"') for var in cppinfo_value]
            if cppinfo_value:
                flags[var.upper()] = [self._conan_prefix_flag(prefix_var) + it for it in cppinfo_value]
                self._makeinfo.flags.append(var)
        return flags

    def generate(self):
        dirs = self._get_component_dirs()
        flags = self._get_component_flags()
        comp_content_gen = DepComponentContentGenerator(self._conanfile, self._dep, self._name, self._comp, self._root, dirs, flags)
        comp_content = comp_content_gen.content()
        return comp_content


class DepGenerator:

    def __init__(self, conanfile, requirement, dependency):
        self._conanfile = conanfile
        self._req = requirement
        self._dep = dependency
        self._info = MakeInfo(self._dep.ref.name, [], [])

    def make_global_info(self):
        self._info.dirs = list(set(self._info.dirs))
        self._info.flags = list(set(self._info.flags))
        return self._info

    def _conan_prefix_flag(self, variable):
        """
        Return a global flag to be used as prefix to any value in the makefile
        """
        return f"$(CONAN_{variable.upper()}_FLAG)" if variable else ""

    def _get_dependency_dirs(self, root, dependency):
        """
        List regular directories from cpp_info and format them to be used in the makefile
        :param root: Package root folder
        :param dep: Dependency object
        """
        dirs = {}
        for var in ['includedirs', 'libdirs', 'bindirs', 'srcdirs', 'builddirs', 'resdirs', 'frameworkdirs']:
            cppinfo_value = getattr(dependency.cpp_info, var)
            formatted_dirs = _get_formatted_dirs(cppinfo_value, root, _makefy(dependency.ref.name))
            if formatted_dirs:
                self._info.dirs.append(var)
                var = var.replace("dirs", "_dirs")
                dirs[var] = [self._conan_prefix_flag(var) + it for it in formatted_dirs]
        return dirs

    def _get_dependency_flags(self, dependency):
        """
        List common variables from cpp_info and format them to be used in the makefile
        :param dep: Dependency object
        """
        common_variables = {
            "objects": None,
            "libs": "lib",
            "system_libs": "system_lib",
            "defines": "define",
            "cflags": None,
            "cxxflags": None,
            "sharedlinkflags": None,
            "exelinkflags": None,
            "frameworks": None,
            "requires": None,
        }
        flags = {}
        for var, prefix_var in common_variables.items():
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
                flags[var.upper()] = [prefix_var + it for it in cppinfo_value]
        return flags

    def _get_sysroot(self, root):
        """
        Get the sysroot of the dependency. Sysroot is a list of directories, or a single directory
        """
        sysroot = self._dep.cpp_info.sysroot if isinstance(self._dep.cpp_info.sysroot, list) else [self._dep.cpp_info.sysroot]
        # sysroot may return ['']
        if not sysroot or not sysroot[0]:
            return None
        return _get_formatted_dirs(sysroot, root, _makefy(self._dep.ref.name)) if sysroot and [0] else None

    def _get_root_folder(self):
        """
        Get the root folder of the dependency
        """
        root = self._dep.recipe_folder if self._dep.package_folder is None else self._dep.package_folder
        return root.replace("\\", "/")

    def generate(self):
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

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        self._conanfile = conanfile

    def _var_ref(self, var):
        return f"$({var})"

    def _var_assign_single(self, var, value):
        return f"{var} = {value}"

    def _var_assign_multi(self, var, value):
        return " \\\n\t".join([f"{var} ="] + value)

    def generate(self):
        check_duplicated_generator(self, self._conanfile)

        line_buffer = []
        var_aggregates = {}

        def _divert():
            buf = list(line_buffer)
            line_buffer.clear()
            return buf

        # Convert a name to Make-variable-friendly syntax
        def _makeify(name):
            return re.sub(r'[^0-9A-Z_]', '_', name.upper())

        # Replace common prefixes in a path list with a variable reference
        def _rootify(root, root_id, path_list):
            root_len = len(root)
            root_with_sep = root + os.path.sep
            root_var_ref = self._var_ref(f"CONAN_ROOT_{root_id}")
            return [root_var_ref + path[root_len:]  \
                    if path.startswith(root_with_sep) else path for path in path_list]

        # Output a variable assignment, appropriately formatted
        def _output_var(name, item, root=None, root_id=None, prefix_var=None, blank_after=True):
            if item is None:
                return False
            if type(item).__name__ in ('Component', 'SettingsItem', 'Version', 'str'):
                value = str(item)
                if not value:
                    return False
                line_buffer.append(self._var_assign_single(name, value))
            else:
                assert type(item) is list
                ritem = _rootify(root, root_id, item) if root else item
                if prefix_var:
                    ritem = [self._var_ref(prefix_var) + i for i in ritem]
                if len(ritem) == 0:
                    return False
                elif len(ritem) == 1:
                    line_buffer.append(self._var_assign_single(name, ritem[0]))
                else:
                    line_buffer.append(self._var_assign_multi(name, ritem))
            if blank_after:
                line_buffer.append("")
            return True

        def _output_cpp_info_vars(var_id, cpp_info, root=None, root_id=None, add_to_aggregates=True, dep=None):

            def _var(name, item, prefix_var=None):
                v = f"CONAN_{name}_{var_id}"

                if _output_var(v, item, root, root_id, prefix_var) and add_to_aggregates:
                    var_aggregates.setdefault(name, []).append(self._var_ref(v))

            prefix_path = root.replace("\\", "/")

            # INFO: sysroot is a list with an empty string as default value
            sysroot = cpp_info.sysroot if isinstance(cpp_info.sysroot, list) else [cpp_info.sysroot]
            if sysroot and sysroot[0]:
                sysroot = _get_formatted_dirs(sysroot, prefix_path, _makeify(dep.ref.name))
                _var("SYSROOT", sysroot)

            for var in ['INCLUDE_DIRS', 'LIB_DIRS', 'BIN_DIRS', 'SRC_DIRS', 'BUILD_DIRS', 'RES_DIRS', 'FRAMEWORK_DIRS']:
                cppinfo_value = getattr(cpp_info, var.replace('_', '').lower())
                dirs = _get_formatted_dirs(cppinfo_value, prefix_path, _makeify(dep.ref.name))
                _var(var, dirs, f"CONAN_{var}_FLAG")

            # TODO: Collect from components if possible
            common_variables = {
                "OBJECTS": None,
                "LIBS": "CONAN_LIB_FLAG",
                "SYSTEM_LIBS": "CONAN_SYSTEM_LIB_FLAG",
                "DEFINES": "CONAN_DEFINE_FLAG",
                "CFLAGS": None,
                "CXXFLAGS": None,
                "SHAREDLINKFLAGS": None,
                "EXELINKFLAGS": None,
                "FRAMEWORKS": None,
                "REQUIRES": None,
            }

            for var, prefix_var in common_variables.items():
                cppinfo_value = getattr(cpp_info, var.lower())
                # Use component cpp_info info when does not provide any value
                if not cppinfo_value and hasattr(cpp_info, "components"):
                    cppinfo_value = [self._var_ref(f"CONAN_{var}_{_makeify(var_id)}_{_makeify(name)}") for name, obj in cpp_info.components.items() if getattr(obj, var.lower())]
                    # avoid repeating same prefix twice
                    prefix_var = None
                if "FLAGS" in var:
                    cppinfo_value = [var.replace('"', '\\"') for var in cppinfo_value]
                _var(var, cppinfo_value, prefix_var)

        # Top-of-file banner
        line_buffer.append(self._title)
        preamble = _divert()

        body = []
        dep_name_list = []

        host_req = self._conanfile.dependencies.host
        build_req = self._conanfile.dependencies.build  # tool_requires
        test_req = self._conanfile.dependencies.test

        require_list = []

        # Filter the build_requires not activated for any requirement
        dependencies = [tup for tup in list(host_req.items()) + list(build_req.items()) + list(test_req.items()) if not tup[0].build]

        make_infos = []

        for require, dep in dependencies:
            # Require is not used at the moment, but its information could be used,
            # and will be used in Conan 2.0

            if require.build:
                continue

            require_list.append(require)
            dep_gen = DepGenerator(self._conanfile, require, dep)
            content = dep_gen.generate()
            save(self._conanfile, path=f"{require.ref.name}.mk", content=content)

            dep_id = _makeify(require.ref.name)
            dep_name_list.append(require.ref.name)

            root = dep.recipe_folder if dep.package_folder is None else dep.package_folder

            line_buffer.extend([
                "",
                f"# {require.ref.name}/{require.ref.version}",
                f"# (" + ("direct" if require.direct else "indirect") + " dependency)",
                ""
            ])

            _output_var(f"CONAN_NAME_{dep_id}", require.ref.name)
            _output_var(f"CONAN_VERSION_{dep_id}", require.ref.version)
            _output_var(f"CONAN_ROOT_{dep_id}", root)

            _output_cpp_info_vars(dep_id, dep.cpp_info, root, dep_id, True, dep)

            dep_section = _divert()
            comp_name_list = []

            for comp_name, component in dep.cpp_info.get_sorted_components().items():
                line_buffer.append(f"# {require.ref.name}::{comp_name}")
                line_buffer.append("")
                comp_id = _makeify(comp_name)
                comp_name_list.append(comp_name)
                _output_cpp_info_vars(f"{dep_id}_{comp_id}", component, root, dep_id, False, dep)

            comp_section = _divert()

            line_buffer.extend(dep_section)
            _output_var(f"CONAN_COMPONENTS_{dep_id}", comp_name_list)
            line_buffer.extend(comp_section)

            body.extend(_divert())

            make_infos.append(dep_gen.make_global_info())

        glob_gen = GlobalGenerator(self._conanfile, make_infos)
        content = glob_gen.deps_generate() + "\n" + glob_gen.generate()
        save(self._conanfile, path="global.mk", content=content)

        assert not line_buffer
        line_buffer.extend([
            "",
            "# Aggregated global values",
            ""
        ])
        for var_name, var_list in var_aggregates.items():
            _output_var(f"CONAN_{var_name}", var_list)
        body.extend(_divert())

        line_buffer.extend(preamble)
        _output_var("CONAN_DEPS", dep_name_list)
        line_buffer.extend(body)

        save(self._conanfile, CONAN_MAKEFILE_FILENAME, "\n".join(line_buffer))
        self._conanfile.output.info(f"Generated {CONAN_MAKEFILE_FILENAME}")
