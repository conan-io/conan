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

from conan.tools.gnu.gnudeps_flags import GnuDepsFlags
from conans.errors import ConanException
from conans.util.files import save


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

    def _get_require_comp_name(self, dep, req):
        # FIXME: this str() is only needed for python2.7 (unicode values). Remove it for Conan 2.0
        pkg_name = str(dep.ref.name)
        pkg, comp_name = req.split("::") if "::" in req else (pkg_name, req)
        # FIXME: it could allow defining requires to not direct dependencies
        req = self._conanfile.dependencies.host[pkg]
        cmp_name = get_component_alias(req, comp_name)
        return cmp_name

    def _get_components(self, dep):
        ret = []
        for comp_name, comp in dep.new_cpp_info.get_sorted_components().items():
            comp_genname = get_component_alias(dep, comp_name)
            comp_requires_gennames = []
            for require in comp.requires:
                comp_requires_gennames.append(self._get_require_comp_name(dep, require))
            ret.append((comp_genname, comp, comp_requires_gennames))
        return ret

    def _get_public_require_deps(self, dep):
        public_comp_deps = []

        for require in dep.new_cpp_info.requires:
            if "::" in require:  # Points to a component of a different package
                pkg, cmp_name = require.split("::")
                req = dep.dependencies.direct_host[pkg]
                public_comp_deps.append(
                    (get_target_namespace(req), get_component_alias(req, cmp_name)))
            else:  # Points to a component of same package
                public_comp_deps.append((get_target_namespace(dep),
                                         get_component_alias(dep, require)))
        return public_comp_deps

    @property
    def content(self):
        ret = {}
        host_req = self._conanfile.dependencies.host
        for require, dep in host_req.items():
            pkg_genname = get_target_namespace(dep)

            if dep.new_cpp_info.has_components:
                components = self._get_components(dep)
                for comp_genname, comp_cpp_info, comp_requires_gennames in components:
                    pkg_comp_genname = "%s-%s" % (pkg_genname, comp_genname)
                    ret["%s.pc" % pkg_comp_genname] = self._pc_file_content(
                        pkg_comp_genname, comp_cpp_info,
                        comp_requires_gennames, dep.package_folder,
                        dep.ref.version)
                comp_gennames = [comp_genname for comp_genname, _, _ in components]
                if pkg_genname not in comp_gennames:
                    ret["%s.pc" % pkg_genname] = self._global_pc_file_contents(pkg_genname,
                                                                               dep,
                                                                               comp_gennames)
            else:
                require_public_deps = [_d for _, _d in
                                       self._get_public_require_deps(dep)]
                ret["%s.pc" % pkg_genname] = self._pc_file_content(pkg_genname, dep.new_cpp_info,
                                                                   require_public_deps,
                                                                   dep.package_folder,
                                                                   dep.ref.version)
        return ret

    def _pc_file_content(self, name, cpp_info, requires_gennames, package_folder, version):
        prefix_path = package_folder.replace("\\", "/")
        lines = ['prefix=%s' % prefix_path]

        gnudeps_flags = GnuDepsFlags(self._conanfile, cpp_info)

        libdir_vars = []
        dir_lines, varnames = self._generate_dir_lines(prefix_path, "libdir", cpp_info.libdirs)
        if dir_lines:
            libdir_vars = varnames
            lines.extend(dir_lines)

        includedir_vars = []
        dir_lines, varnames = self._generate_dir_lines(prefix_path, "includedir",
                                                       cpp_info.includedirs)
        if dir_lines:
            includedir_vars = varnames
            lines.extend(dir_lines)

        pkg_config_custom_content = cpp_info.get_property("pkg_config_custom_content",
                                                          "PkgConfigDeps")
        if pkg_config_custom_content:
            lines.append(pkg_config_custom_content)

        lines.append("")
        lines.append("Name: %s" % name)
        description = self._conanfile.description or "Conan package: %s" % name
        lines.append("Description: %s" % description)
        lines.append("Version: %s" % version)
        libdirs_flags = ['-L"${%s}"' % name for name in libdir_vars]
        lib_paths = ["${%s}" % libdir for libdir in libdir_vars]
        libnames_flags = ["-l%s " % name for name in (cpp_info.libs + cpp_info.system_libs)]
        shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags

        lines.append("Libs: %s" % _concat_if_not_empty([libdirs_flags,
                                                        libnames_flags,
                                                        shared_flags,
                                                        gnudeps_flags._rpath_flags(lib_paths),
                                                        gnudeps_flags.frameworks,
                                                        gnudeps_flags.framework_paths]))
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

    def _global_pc_file_contents(self, name, dep, comp_gennames):
        lines = ["Name: %s" % name]
        description = self._conanfile.description or "Conan package: %s" % name
        lines.append("Description: %s" % description)
        lines.append("Version: %s" % dep.ref.version)

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

    def generate(self):
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)
