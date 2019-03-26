import os

from conans.client.build.compiler_flags import rpath_flags
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
            ret["%s.pc" % depname] = self.single_pc_file_contents(depname, cpp_info)
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
        libnames_flags = ["-l%s " % name for name in cpp_info.libs]
        shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags
        the_os = (self.conanfile.settings.get_safe("os_build") or
                  self.conanfile.settings.get_safe("os"))
        rpaths = rpath_flags(the_os, self.compiler, ["${%s}" % libdir for libdir in libdir_vars])
        lines.append("Libs: %s" % _concat_if_not_empty([libdirs_flags,
                                                        libnames_flags,
                                                        shared_flags,
                                                        rpaths]))
        include_dirs_flags = ["-I${%s}" % name for name in includedir_vars]

        lines.append("Cflags: %s" % _concat_if_not_empty(
            [include_dirs_flags,
             cpp_info.cxxflags,
             cpp_info.cflags,
             ["-D%s" % d for d in cpp_info.defines]]))

        if cpp_info.public_deps:
            public_deps = " ".join(cpp_info.public_deps)
            lines.append("Requires: %s" % public_deps)
        return "\n".join(lines) + "\n"


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
