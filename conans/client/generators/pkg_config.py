import os

from conans.client.build.compiler_flags import rpath_flags, format_frameworks, format_framework_paths
from conans.client.tools.oss import get_build_os_arch
from conans.errors import ConanException
from conans.model import Generator
from conans.model.build_info import COMPONENT_SCOPE

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


class PkgConfigGenerator(Generator):
    name = "pkg_config"

    @property
    def filename(self):
        return None

    @property
    def compiler(self):
        return self.conanfile.settings.get_safe("compiler")

    @classmethod
    def _get_name(cls, obj):
        get_name = getattr(obj, "get_name")
        return get_name(cls.name)

    def _get_components(self, pkg_name, cpp_info):
        generator_components = []
        for comp_name, comp in self.sorted_components(cpp_info).items():
            comp_genname = self._get_name(cpp_info.components[comp_name])
            comp_requires_gennames = self._get_component_requires(pkg_name, comp)
            generator_components.append((comp_genname, comp, comp_requires_gennames))
        generator_components.reverse()  # From the less dependent to most one
        return generator_components

    def _get_component_requires(self, pkg_name, comp):
        comp_requires_gennames = []
        for require in comp.requires:
            if COMPONENT_SCOPE in require:
                comp_require_pkg_name, comp_require_comp_name = require.split(COMPONENT_SCOPE)
                comp_require_pkg = self.deps_build_info[comp_require_pkg_name]
                comp_require_pkg_genname = self._get_name(comp_require_pkg)
                if comp_require_comp_name == comp_require_pkg_name:
                    comp_require_comp_genname = comp_require_pkg_genname
                elif comp_require_comp_name in self.deps_build_info[comp_require_pkg_name].components:
                    comp_require_comp = comp_require_pkg.components[comp_require_comp_name]
                    comp_require_comp_genname = self._get_name(comp_require_comp)
                else:
                    raise ConanException("Component '%s' not found in '%s' package requirement"
                                         % (require, comp_require_pkg_name))
            else:
                comp_require_comp = self.deps_build_info[pkg_name].components[require]
                comp_require_comp_genname = self._get_name(comp_require_comp)
            comp_requires_gennames.append(comp_require_comp_genname)
        return comp_requires_gennames

    @property
    def content(self):
        ret = {}
        for depname, cpp_info in self.deps_build_info.dependencies:
            pkg_genname = cpp_info.get_name(PkgConfigGenerator.name)
            if not cpp_info.components:
                ret["%s.pc" % pkg_genname] = self.single_pc_file_contents(pkg_genname, cpp_info,
                                                                          cpp_info.public_deps)
            else:
                components = self._get_components(depname, cpp_info)
                for comp_genname, comp, comp_requires_gennames in components:
                    ret["%s.pc" % comp_genname] = self.single_pc_file_contents(
                        "%s-%s" % (pkg_genname, comp_genname),
                        comp,
                        comp_requires_gennames,
                        is_component=True)
                comp_gennames = [comp_genname for comp_genname, _, _ in components]
                if pkg_genname not in comp_gennames:
                    ret["%s.pc" % pkg_genname] = self.global_pc_file_contents(pkg_genname, cpp_info,
                                                                              comp_gennames)
        return ret

    def single_pc_file_contents(self, name, cpp_info, comp_requires_gennames, is_component=False):
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

        lines.append("")
        lines.append("Name: %s" % name)
        description = cpp_info.description or "Conan package: %s" % name
        lines.append("Description: %s" % description)
        lines.append("Version: %s" % cpp_info.version)
        libdirs_flags = ["-L${%s}" % name for name in libdir_vars]
        libnames_flags = ["-l%s " % name for name in (cpp_info.libs + cpp_info.system_libs)]
        shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags

        os_build, _ = get_build_os_arch(self.conanfile)
        if not hasattr(self.conanfile, 'settings_build'):
            os_build = os_build or self.conanfile.settings.get_safe("os")

        rpaths = rpath_flags(self.conanfile.settings, os_build,
                             ["${%s}" % libdir for libdir in libdir_vars])
        frameworks = format_frameworks(cpp_info.frameworks, self.conanfile.settings)
        framework_paths = format_framework_paths(cpp_info.framework_paths, self.conanfile.settings)

        lines.append("Libs: %s" % _concat_if_not_empty([libdirs_flags,
                                                        libnames_flags,
                                                        shared_flags,
                                                        rpaths,
                                                        frameworks,
                                                        framework_paths]))
        include_dirs_flags = ["-I${%s}" % name for name in includedir_vars]

        lines.append("Cflags: %s" % _concat_if_not_empty(
            [include_dirs_flags,
             cpp_info.cxxflags,
             cpp_info.cflags,
             ["-D%s" % d for d in cpp_info.defines]]))

        if comp_requires_gennames:
            if is_component:
                pkg_config_names = comp_requires_gennames
            else:
                pkg_config_names = []
                for public_dep in cpp_info.public_deps:
                    name = self.deps_build_info[public_dep].get_name(PkgConfigGenerator.name)
                    pkg_config_names.append(name)
            public_deps = " ".join(pkg_config_names)
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


def _concat_if_not_empty(groups):
    return " ".join([param for group in groups for param in group if param and param.strip()])
