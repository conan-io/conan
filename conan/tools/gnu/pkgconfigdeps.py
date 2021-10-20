"""
    PkgConfigDeps Conan generator

    - PC FILE EXAMPLE:

        prefix=/usr
        exec_prefix=${prefix}
        libdir=${exec_prefix}/lib
        includedir=${prefix}/include

        Name: my-project
        Description: Some brief but informative description
        Version: 1.2.3
        Libs: -L${libdir} -lmy-project-1 -linkerflag -Wl,-rpath=${libdir}
        Cflags: -I${includedir}/my-project-1
        Requires: glib-2.0 >= 2.40 gio-2.0 >= 2.42 nice >= 0.1.6
        Requires.private: gthread-2.0 >= 2.40
"""
import os
import textwrap

from jinja2 import Template, StrictUndefined

from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.errors import ConanException
from conans.util.files import save


def get_target_namespace(req):
    ret = req.cpp_info.get_property("pkg_config_name", "PkgConfigDeps")
    return ret or req.ref.name


def get_component_alias(req, comp_name):
    if comp_name not in req.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if req.ref.name == comp_name:
            return get_target_namespace(req)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=req.ref.name, cname=comp_name))
    ret = req.cpp_info.components[comp_name].get_property("pkg_config_name", "PkgConfigDeps")
    return ret or comp_name


class PkgConfigDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @staticmethod
    def _get_composed_pkg_config_name(pkg_name, comp_name):
        """Build a composed name for all the components and its package root name"""
        return "%s-%s" % (pkg_name, comp_name)

    def _get_requires_names(self, dep, cpp_info=None):
        """
        Get all the pkg-config valid names from the requires ones given a dependency and
        a CppInfo object.

        Note: CppInfo could be coming from one Component object instead of the dependency
        """
        ret = []
        cpp_info = cpp_info or dep.cpp_info
        for req in cpp_info.requires:
            # FIXME: this str(dep.ref.name) is only needed for python2.7 (unicode values).
            #        Remove it for Conan 2.0
            pkg_name, comp_name = req.split("::") if "::" in req else (str(dep.ref.name), req)
            # FIXME: it could allow defining requires to not direct dependencies
            req_conanfile = self._conanfile.dependencies.host[pkg_name]
            comp_alias_name = get_component_alias(req_conanfile, comp_name)
            ret.append(self._get_composed_pkg_config_name(pkg_name, comp_alias_name))
        return ret

    def get_components_pc_files(self, dep):
        """Get all the *.pc files for the dependency and each of its components"""
        pc_files = {}
        pkg_name = get_target_namespace(dep)
        comp_names = []
        pc_gen = _PCGenerator(self._conanfile, dep)
        # Loop through all the dependency components
        for comp_name, comp_cpp_info in dep.cpp_info.get_sorted_components().items():
            comp_name = get_component_alias(dep, comp_name)
            comp_names.append(comp_name)
            comp_requires_names = self._get_requires_names(dep, comp_cpp_info)
            pkg_comp_name = self._get_composed_pkg_config_name(pkg_name, comp_name)
            # Save the *.pc file for this component
            pc_files.update(pc_gen.complete_pc_content(comp_requires_names, name=pkg_comp_name,
                                                       cpp_info=comp_cpp_info))
        # Adding the dependency *.pc file (including its components as requires if any)
        if pkg_name not in comp_names:
            pkg_requires = [self._get_composed_pkg_config_name(pkg_name, i) for i in comp_names]
            pc_files.update(pc_gen.simple_pc_content(pkg_requires))
        return pc_files

    @property
    def content(self):
        pc_files = {}
        host_req = self._conanfile.dependencies.host
        for require, dep in host_req.items():
            if dep.cpp_info.has_components:
                pc_files.update(self.get_components_pc_files(dep))
            else:
                pc_gen = _PCGenerator(self._conanfile, dep)
                requires = self._get_requires_names(dep)
                pc_files.update(pc_gen.complete_pc_content(requires))
        return pc_files

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)


class _PCGenerator(object):

    def __init__(self, conanfile, dep):
        self._conanfile = conanfile
        self._dep = dep
        self._name = get_target_namespace(dep)

    complete_pc_template = textwrap.dedent("""\
    prefix={{prefix_path}}
    {% for name, path in libdirs %}
    {{ name + "=" + path }}
    {% endfor %}
    {% for name, path in includedirs %}
    {{ name + "=" + path }}
    {% endfor %}
    {% if pkg_config_custom_content %}
    # Custom PC content
    {{pkg_config_custom_content}}
    {% endif %}

    Name: {{name}}
    Description: {{description}}
    Version: {{version}}
    Libs: {{ libs }}
    Cflags: {{ cflags }}
    {% if requires|length %}
    Requires: {% for dep in requires %}{{ dep }}{%- if not loop.last %} {% endif %}{% endfor %}
    {% endif %}
    """)

    simple_pc_template = textwrap.dedent("""\
    Name: {{name}}
    Description: {{description}}
    Version: {{version}}
    {% if requires|length %}
    Requires: {% for dep in requires %}{{ dep }}{%- if not loop.last %} {% endif %}{% endfor %}
    {% endif %}
    """)

    def complete_pc_content(self, requires, name=None, cpp_info=None):

        def _concat_if_not_empty(groups):
            return " ".join(
                [param for group in groups for param in group if param and param.strip()])

        def get_libs(libdirs_):
            libdirs_flags = ['-L"${%s}"' % libdir for libdir, _ in libdirs_]
            lib_paths = ["${%s}" % libdir for libdir, _ in libdirs_]
            libnames_flags = ["-l%s " % n for n in (cpp_info.libs + cpp_info.system_libs)]
            shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags

            gnudeps_flags = GnuDepsFlags(self._conanfile, cpp_info)
            return _concat_if_not_empty([libdirs_flags,
                                         libnames_flags,
                                         shared_flags,
                                         gnudeps_flags._rpath_flags(lib_paths),
                                         gnudeps_flags.frameworks,
                                         gnudeps_flags.framework_paths])

        def get_cflags(includedirs_):
            return _concat_if_not_empty(
                [['-I"${%s}"' % n for n, _ in includedirs_],
                 cpp_info.cxxflags,
                 cpp_info.cflags,
                 ["-D%s" % d for d in cpp_info.defines]])

        def get_formmatted_dirs(field, folders, prefix_path_):
            ret = []
            for i, directory in enumerate(folders):
                directory = os.path.normpath(directory).replace("\\", "/")
                n = field if i == 0 else "%s%d" % (field, (i + 1))
                prefix = ""
                if not os.path.isabs(directory):
                    prefix = "${prefix}/"
                elif directory.startswith(prefix_path_):
                    prefix = "${prefix}/"
                    directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
                ret.append((n, "%s%s" % (prefix, directory)))
            return ret

        dep_name = name or self._name
        package_folder = self._dep.package_folder
        version = self._dep.ref.version
        cpp_info = cpp_info or self._dep.cpp_info

        prefix_path = package_folder.replace("\\", "/")
        libdirs = get_formmatted_dirs("libdir", cpp_info.libdirs, prefix_path)
        includedirs = get_formmatted_dirs("includedir", cpp_info.includedirs, prefix_path)

        context = {
            "prefix_path": prefix_path,
            "libdirs": libdirs,
            "includedirs": includedirs,
            "pkg_config_custom_content": cpp_info.get_property("pkg_config_custom_content", "PkgConfigDeps"),
            "name": dep_name,
            "description": self._conanfile.description or "Conan package: %s" % dep_name,
            "version": version,
            "libs": get_libs(libdirs),
            "cflags": get_cflags(includedirs),
            "requires": requires
        }
        template = Template(self.complete_pc_template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return {dep_name + ".pc": template.render(context)}

    def simple_pc_content(self, requires, name=None):
        dep_name = name or self._name
        context = {
            "name": dep_name,
            "description": self._conanfile.description or "Conan package: %s" % dep_name,
            "version": self._dep.ref.version,
            "requires": requires
        }
        template = Template(self.simple_pc_template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        return {dep_name + ".pc": template.render(context)}
