import os

# FIXME: imports from conan namespace
import textwrap

from conans.client.build.compiler_flags import rpath_flags, format_frameworks, format_framework_paths
from conans.client.tools.oss import get_build_os_arch
from conans.errors import ConanException
from conans.util.files import save

"""
PC FILE EXAMPLE:

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


def _concat_if_not_empty(groups):
    return " ".join([param for group in groups for param in group if param and param.strip()])


def get_target_namespace(req):
    ret = req.new_cpp_info.get_property("pkg_config_name", "PkgConfigDeps")
    return ret or req.ref.name


def get_component_alias(req, comp_name):
    if comp_name not in req.new_cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if req.ref.name == comp_name:
            return get_target_namespace(req)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=req.ref.name, cname=comp_name))
    ret = req.new_cpp_info.components[comp_name].get_property("pkg_config_name", "PkgConfigDeps")
    return ret or comp_name


class PkgConfigDeps(object):

    def __init__(self, conanfile):
        self._conanfile = conanfile

    @property
    def compiler(self):
        return self._conanfile.settings.get_safe("compiler")

    def _get_require_comp_name(self, pkg_name, req):
        pkg, comp_name = req.split("::") if "::" in req else (pkg_name, req)
        req = self._conanfile.dependencies.direct_host[pkg]
        cmp_name = get_component_alias(req, comp_name)
        return cmp_name

    def get_components(self, pkg_name, dep):
        ret = []
        for comp_name, comp in dep.new_cpp_info.get_sorted_components().items():
            comp_genname = get_component_alias(dep, comp_name)
            comp_requires_gennames = []
            for require in comp.requires:
                comp_requires_gennames.append(self._get_require_comp_name(pkg_name, require))
            ret.append((comp_genname, comp, comp_requires_gennames))
        return ret

    def _get_public_require_deps(self, comp):
        public_comp_deps = []
        for require in comp.requires:
            if "::" in require:  # Points to a component of a different package
                pkg, cmp_name = require.split("::")
                req = self._conanfile.dependencies.direct_host[pkg]
                public_comp_deps.append(
                    (get_target_namespace(req), get_component_alias(req, cmp_name)))
            else:  # Points to a component of same package
                public_comp_deps.append((get_target_namespace(self._conanfile),
                                         get_component_alias(self._conanfile, require)))
        return public_comp_deps

    @property
    def content(self):
        ret = {}
        host_req = self._conanfile.dependencies.host

        for require, dep in host_req.items():
            pkg_genname = dep.new_cpp_info.get_property("pkg_config_name", "PkgConfigDeps")

            if dep.new_cpp_info.components:
                components = self.get_components(dep.ref.name, dep)
                for comp_genname, comp, comp_requires_gennames in components:
                    ret["%s.pc" % comp_genname] = self._pc_file_content(
                        "%s-%s" % (pkg_genname, comp_genname),
                        comp,
                        comp_requires_gennames)
                comp_gennames = [comp_genname for comp_genname, _, _ in components]
                if pkg_genname not in comp_gennames:
                    ret["%s.pc" % pkg_genname] = self.global_pc_file_contents(pkg_genname,
                                                                              dep.new_cpp_info,
                                                                              comp_gennames)
            else:
                require_public_deps = [_d for _, _d in self._get_public_require_deps(dep.new_cpp_info)]
                ret["%s.pc" % pkg_genname] = self._pc_file_content(pkg_genname, dep.new_cpp_info,
                                                                   require_public_deps)
        return ret

    def _pc_file_content(self, name, cpp_info, requires_gennames):
        prefix_path = cpp_info.rootpath.replace("\\", "/")
        lines = ['prefix=%s' % prefix_path]

        libdir_vars = []
        dir_lines, varnames = self._generate_dir_lines(prefix_path, "libdir", cpp_info.lib_paths)
        if dir_lines:
            libdir_vars = varnames
            lines.extend(dir_lines)

        includedir_vars = []
        dir_lines, varnames = self._generate_dir_lines(prefix_path, "includedir",
                                                       cpp_info.include_paths)
        if dir_lines:
            includedir_vars = varnames
            lines.extend(dir_lines)

        pkg_config_custom_content = cpp_info.get_property("pkg_config_custom_content",
                                                          "PkgConfigDeps")
        if pkg_config_custom_content:
            lines.append(pkg_config_custom_content)

        lines.append("")
        lines.append("Name: %s" % name)
        description = cpp_info.description or "Conan package: %s" % name
        lines.append("Description: %s" % description)
        lines.append("Version: %s" % cpp_info.version)
        libdirs_flags = ['-L"${%s}"' % name for name in libdir_vars]
        libnames_flags = ["-l%s " % name for name in (cpp_info.libs + cpp_info.system_libs)]
        shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags

        os_build, _ = get_build_os_arch(self._conanfile)
        if not hasattr(self._conanfile, 'settings_build'):
            os_build = os_build or self._conanfile.settings.get_safe("os")

        rpaths = rpath_flags(self._conanfile.settings, os_build,
                             ["${%s}" % libdir for libdir in libdir_vars])
        frameworks = format_frameworks(cpp_info.frameworks, self._conanfile.settings)
        framework_paths = format_framework_paths(cpp_info.framework_paths, self._conanfile.settings)

        lines.append("Libs: %s" % _concat_if_not_empty([libdirs_flags,
                                                        libnames_flags,
                                                        shared_flags,
                                                        rpaths,
                                                        frameworks,
                                                        framework_paths]))
        include_dirs_flags = ['-I"${%s}"' % name for name in includedir_vars]

        lines.append("Cflags: %s" % _concat_if_not_empty(
            [include_dirs_flags,
             cpp_info.cxxflags,
             cpp_info.cflags,
             ["-D%s" % d for d in cpp_info.defines]]))

        if requires_gennames:
            public_deps = " ".join(requires_gennames)
            lines.append("Requires: %s" % public_deps)
        return "\n".join(lines) + "\n"

    @staticmethod
    def global_pc_file_contents(name, cpp_info, comp_gennames):
        lines = ["Name: %s" % name]
        description = cpp_info.description or "Conan package: %s" % name
        lines.append("Description: %s" % description)
        lines.append("Version: %s" % cpp_info.version)

        if comp_gennames:
            public_deps = " ".join(comp_gennames)
            lines.append("Requires: %s" % public_deps)
        return "\n".join(lines) + "\n"

    @staticmethod
    def _generate_dir_lines(prefix_path, varname, dirs):
        lines = []
        varnames = []
        for i, directory in enumerate(dirs):
            directory = os.path.normpath(directory).replace("\\", "/")
            name = varname if i == 0 else "%s%d" % (varname, (i + 1))
            prefix = ""
            if not os.path.isabs(directory):
                prefix = "${prefix}/"
            elif directory.startswith(prefix_path):
                prefix = "${prefix}/"
                directory = os.path.relpath(directory, prefix_path).replace("\\", "/")
            lines.append("%s=%s%s" % (name, prefix, directory))
            varnames.append(name)
        return lines, varnames

    @property
    def template(self):
        return textwrap.dedent("""\
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
        """)

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)
