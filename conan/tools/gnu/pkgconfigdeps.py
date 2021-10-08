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

import jinja2
from jinja2 import Template

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
    def _get_composed_require_name(pkg_name, comp_name):
        return "%s-%s" % (pkg_name, comp_name)

    def _get_require_comp_name(self, dep, req):
        # FIXME: this str() is only needed for python2.7 (unicode values). Remove it for Conan 2.0
        pkg_name = str(dep.ref.name)
        pkg, comp_name = req.split("::") if "::" in req else (pkg_name, req)
        # FIXME: it could allow defining requires to not direct dependencies
        req = self._conanfile.dependencies.host[pkg]
        cmp_name = get_component_alias(req, comp_name)
        return self._get_composed_require_name(pkg, cmp_name)

    def _get_components(self, dep):
        ret = []
        for comp_name, comp in dep.cpp_info.get_sorted_components().items():
            comp_genname = get_component_alias(dep, comp_name)
            comp_requires_gennames = []
            for require in comp.requires:
                comp_requires_gennames.append(self._get_require_comp_name(dep, require))
            ret.append((comp_genname, comp, comp_requires_gennames))
        return ret

    def _get_public_require_deps(self, dep):
        public_comp_deps = []

        for require in dep.cpp_info.requires:
            if "::" in require:  # Points to a component of a different package
                pkg, cmp_name = require.split("::")
                req = dep.dependencies.direct_host[pkg]
                public_comp_deps.append(
                    self._get_composed_require_name(pkg, get_component_alias(req, cmp_name))
                )
            else:  # Points to a component of same package
                public_comp_deps.append(get_component_alias(dep, require))
        return public_comp_deps

    @property
    def content(self):
        ret = {}
        host_req = self._conanfile.dependencies.host
        for require, dep in host_req.items():
            pkg_genname = get_target_namespace(dep)

            if dep.cpp_info.has_components:
                components = self._get_components(dep)
                # Adding one *.pc file per component, e.g., pkg-comp1.pc
                for comp_genname, comp_cpp_info, comp_requires_gennames in components:
                    pkg_comp_genname = self._get_composed_require_name(pkg_genname, comp_genname)
                    ret["%s.pc" % pkg_comp_genname] = self._pc_file_content(
                        pkg_comp_genname, comp_cpp_info,
                        comp_requires_gennames,
                        dep.package_folder, dep.ref.version)
                # Adding the pkg *.pc file (including its components as requires if any)
                comp_gennames = [comp_genname for comp_genname, _, _ in components]
                if pkg_genname not in comp_gennames:
                    pkg_requires = (self._get_composed_require_name(pkg_genname, i)
                                    for i in comp_gennames)
                    ret["%s.pc" % pkg_genname] = self._global_pc_file_contents(pkg_genname,
                                                                               dep,
                                                                               pkg_requires)
            else:
                ret["%s.pc" % pkg_genname] = self._pc_file_content(pkg_genname, dep.cpp_info,
                                                                   self._get_public_require_deps(dep),
                                                                   dep.package_folder,
                                                                   dep.ref.version)
        return ret

    @property
    def template_global_content(self):
        return textwrap.dedent("""\
        Name: {{dep_name}}
        Description: {{description}}
        Version: {{dep_version}}
        {% if public_deps %}
        Requires: {% for dep in public_deps %}
                {{ dep }}
            {%- if not loop.last %},{% endif %}
            {% endfor %}
        {% endif %}
        """)

    @property
    def template_content(self):
        return textwrap.dedent("""\
        prefix={{prefix_path}}
        {%- for name, path in libdirs.items() %}
            {{ name + "=" + path }}
        {% endfor %}
        {%- for name, path in includedirs.items() %}
            {{ name + "=" + path }}
        {% endfor %}
        {% if pkg_config_custom_content %}
        # Custom PC content
        {{pkg_config_custom_content}}
        {% endif %}

        Name: {{dep_name}}
        Description: {{description}}
        Version: {{dep_version}}
        Libs: {{ libs }}
        Cflags: {{ flags }}
        {% if public_deps %}
        Requires: {% for dep in public_deps %}
                {{ dep }}
            {%- if not loop.last %},{% endif %}
            {% endfor %}
        {% endif %}
        """)

    def _pc_file_content(self, name, cpp_info, requires_gennames, package_folder, version):

        def _concat_if_not_empty(groups):
            return " ".join(
                [param for group in groups for param in group if param and param.strip()])

        def get_libs(libdirs):
            libdirs_flags = ['-L"${%s}"' % libdir for libdir in libdirs]
            lib_paths = ["${%s}" % libdir for libdir in libdirs]
            libnames_flags = ["-l%s " % name for name in (cpp_info.libs + cpp_info.system_libs)]
            shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags

            gnudeps_flags = GnuDepsFlags(self._conanfile, cpp_info)
            return _concat_if_not_empty([libdirs_flags,
                                         libnames_flags,
                                         shared_flags,
                                         gnudeps_flags._rpath_flags(lib_paths),
                                         gnudeps_flags.frameworks,
                                         gnudeps_flags.framework_paths])

        def get_cflags(includedirs):
            return _concat_if_not_empty(
                [['-I"${%s}"' % name for name in includedirs],
                 cpp_info.cxxflags,
                 cpp_info.cflags,
                 ["-D%s" % d for d in cpp_info.defines]])

        def get_formmatted_dirs(field, folders, prefix_path_):
            ret = {}
            for i, directory in enumerate(folders):
                directory = os.path.normpath(directory).replace("\\", "/")
                name = field if i == 0 else "%s%d" % (field, (i + 1))
                prefix = ""
                if not os.path.isabs(directory):
                    prefix = "${prefix}/"
                elif directory.startswith(prefix_path_):
                    prefix = "${prefix}/"
                    directory = os.path.relpath(directory, prefix_path_).replace("\\", "/")
                ret[name] = "%s%s" % (prefix, directory)
            return ret

        def context():
            prefix_path = package_folder.replace("\\", "/")
            libdirs = get_formmatted_dirs("libdir", cpp_info.libdirs, prefix_path)
            includedirs = get_formmatted_dirs("includedir", cpp_info.includedirs, prefix_path)

            return {
                "prefix_path": prefix_path,
                "libdirs": libdirs,
                "includedirs": includedirs,
                "pkg_config_custom_content": cpp_info.get_property("pkg_config_custom_content",
                                                                   "PkgConfigDeps"),
                "name": name,
                "description": self._conanfile.description or "Conan package: %s" % name,
                "version": version,
                "libs": get_libs(libdirs),
                "cflags": get_cflags(includedirs),
                "public_deps": requires_gennames
            }

        return Template(self.template_content, trim_blocks=True, lstrip_blocks=True,
                        undefined=jinja2.StrictUndefined).render(context)

    def _global_pc_file_contents(self, name, dep, comp_gennames):
        context = {
            "name": name,
            "description": self._conanfile.description or "Conan package: %s" % name,
            "version": dep.ref.version,
            "public_deps": comp_gennames
        }

        return Template(self.template_global_content, trim_blocks=True, lstrip_blocks=True,
                        undefined=jinja2.StrictUndefined).render(context)

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)
