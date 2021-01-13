from conans.model import Generator


class MakeGenerator(Generator):

    def __init__(self, conanfile):
        Generator.__init__(self, conanfile)
        self.makefile_newline = "\n"
        self.makefile_line_continuation = " \\\n"
        self.assignment_if_absent = " ?= "
        self.assignment_append = " += "

    @property
    def filename(self):
        return 'conanbuildinfo.mak'

    @property
    def content(self):
        content = [
            "#-------------------------------------------------------------------#",
            "#             Makefile variables from Conan Dependencies            #",
            "#-------------------------------------------------------------------#",
            "",
        ]

        deps_content = []
        for pkg_name, cpp_info in self.deps_build_info.dependencies:
            deps_content.extend(self._create_content_from_dep(pkg_name, cpp_info))

        deps_content.extend(self._create_combined_content())
        for line_as_list in deps_content:
            content.append("".join(line_as_list))

        content.append("#-------------------------------------------------------------------#")
        content.append(self.makefile_newline)
        return self.makefile_newline.join(content)

    def _create_content_from_dep(self, pkg_name, cpp_info):
        vars_info = [("ROOT", self.assignment_if_absent, [cpp_info.rootpath]),
                     ("SYSROOT", self.assignment_if_absent, [cpp_info.sysroot]),
                     ("INCLUDE_DIRS", self.assignment_append, cpp_info.include_paths),
                     ("LIB_DIRS", self.assignment_append, cpp_info.lib_paths),
                     ("BIN_DIRS", self.assignment_append, cpp_info.bin_paths),
                     ("BUILD_DIRS", self.assignment_append, cpp_info.build_paths),
                     ("RES_DIRS", self.assignment_append, cpp_info.res_paths),
                     ("LIBS", self.assignment_append, cpp_info.libs),
                     ("SYSTEM_LIBS", self.assignment_append, cpp_info.system_libs),
                     ("DEFINES", self.assignment_append, cpp_info.defines),
                     ("CFLAGS", self.assignment_append, cpp_info.cflags),
                     ("CXXFLAGS", self.assignment_append, cpp_info.cxxflags),
                     ("SHAREDLINKFLAGS", self.assignment_append, cpp_info.sharedlinkflags),
                     ("EXELINKFLAGS", self.assignment_append, cpp_info.exelinkflags),
                     ("FRAMEWORKS", self.assignment_append, cpp_info.frameworks),
                     ("FRAMEWORK_PATHS", self.assignment_append, cpp_info.framework_paths)]

        return [self._create_makefile_var(var_name, operator, values, pkg=pkg_name)
                for var_name, operator, values in vars_info]

    def _create_combined_content(self):
        content = []
        for var_name in ["root", "sysroot", "include_dirs", "lib_dirs", "bin_dirs", "build_dirs",
                         "res_dirs", "libs", "defines", "cflags", "cxxflags", "sharedlinkflags",
                         "exelinkflags", "frameworks", "framework_paths", "system_libs"]:
            values = ["$(CONAN_{var}_{pkg})".format(var=var_name.upper(), pkg=pkg.upper())
                      for pkg, _ in self.deps_build_info.dependencies]
            content.append(self._create_makefile_var(var_name, self.assignment_append, values))
        return content

    def _create_makefile_var(self, var_name, operator, values, pkg=None):
        pkg = "_{}".format(pkg.upper()) if pkg else ""
        make_var = ["CONAN_{var}{pkg}{op}".format(var=var_name.upper(), pkg=pkg, op=operator)]
        make_var.extend(value.replace("\\", "/") for value in values)
        return self.makefile_line_continuation.join(make_var) + self.makefile_newline
