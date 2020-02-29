import os

from conans.client.build.compiler_flags import rpath_flags, format_frameworks, format_framework_paths
from conans.model import Generator

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

    @property
    def filename(self):
        pass

    @property
    def compiler(self):
        return self.conanfile.settings.get_safe("compiler")

    @property
    def content(self):
        ret = {}
        for depname, cpp_info in self.deps_build_info.dependencies:
            name = _get_name(depname, cpp_info)
            ret["%s.pc" % name] = self.single_pc_file_contents(name, cpp_info)
        return ret

    def single_pc_file_contents(self, name, cpp_info):
        prefix_path = cpp_info.rootpath.replace("\\", "/")
        lines = ['prefix=%s' % prefix_path]

        libdir_vars = []
        dir_lines, varnames = _generate_dir_lines(prefix_path, "libdir", cpp_info.libdirs)
        if dir_lines:
            libdir_vars = varnames
            lines.extend(dir_lines)

        includedir_vars = []
        dir_lines, varnames = _generate_dir_lines(prefix_path, "includedir", cpp_info.includedirs)
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
        the_os = (self.conanfile.settings.get_safe("os_build") or
                  self.conanfile.settings.get_safe("os"))
        rpaths = rpath_flags(the_os, self.compiler, ["${%s}" % libdir for libdir in libdir_vars])
        frameworks = format_frameworks(cpp_info.frameworks, compiler=self.compiler)
        framework_paths = format_framework_paths(cpp_info.framework_paths, compiler=self.compiler)
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

        if cpp_info.public_deps:
            pkg_config_names = []
            for public_dep in cpp_info.public_deps:
                pkg_config_names.append(_get_name(public_dep, self.deps_build_info[public_dep]))
            public_deps = " ".join(pkg_config_names)
            lines.append("Requires: %s" % public_deps)
        return "\n".join(lines) + "\n"


def _get_name(depname, cpp_info):
    # the name for the pc will be converted to lowercase when cpp_info.name is specified
    # but with cpp_info.names["pkg_config"] will be literal
    if "pkg_config" in cpp_info.names:
        name = cpp_info.names["pkg_config"]
    else:
        name = cpp_info.name.lower() if cpp_info.name != depname else depname
    return name


def _concat_if_not_empty(groups):
    return " ".join([param for group in groups for param in group if param and param.strip()])


def _generate_dir_lines(prefix_path, varname, dirs):
    lines = []
    varnames = []
    for i, directory in enumerate(dirs):
        directory = os.path.normpath(directory).replace("\\", "/")
        varname = varname if i == 0 else "%s%d" % (varname, (i + 2))
        prefix = ""
        if not os.path.isabs(directory):
            prefix = "${prefix}/"
        elif directory.startswith(prefix_path):
            prefix = "${prefix}/"
            directory = os.path.relpath(directory, prefix_path)
        lines.append("%s=%s%s" % (varname, prefix, directory))
        varnames.append(varname)
    return lines, varnames
