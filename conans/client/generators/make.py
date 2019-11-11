from conans.model import Generator
from conans.paths import BUILD_INFO_MAKE


class MakeGenerator(Generator):

    def __init__(self, conanfile):
        Generator.__init__(self, conanfile)
        self.makefile_newline = "\n"
        self.makefile_line_continuation = " \\\n"
        self.assignment_if_absent = " ?= "
        self.assignment_append = " += "

    @property
    def filename(self):
        return BUILD_INFO_MAKE

    @property
    def content(self):

        content = [
            "#-------------------------------------------------------------------#",
            "#             Makefile variables from Conan Dependencies            #",
            "#-------------------------------------------------------------------#",
            "",
        ]

        for line_as_list in self.create_deps_content():
            content.append("".join(line_as_list))

        content.append("#-------------------------------------------------------------------#")
        content.append(self.makefile_newline)
        return self.makefile_newline.join(content)

    def create_deps_content(self):
        deps_content = self.create_content_from_deps()
        deps_content.extend(self.create_combined_content())
        return deps_content

    def create_content_from_deps(self):
        content = []
        for pkg_name, cpp_info in self.deps_build_info.dependencies:
            content.extend(self.create_content_from_dep(pkg_name, cpp_info))
        return content

    def create_content_from_dep(self, pkg_name, cpp_info):

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

        return [self.create_makefile_var_pkg(var_name, pkg_name, operator, info)
                for var_name, operator, info in vars_info]

    def create_combined_content(self):
        content = []
        for var_name in self.all_dep_vars():
            content.append(self.create_makefile_var_global(var_name, self.assignment_append,
                                                           self.create_combined_var_list(var_name)))
        return content

    def create_combined_var_list(self, var_name):
        make_vars = []
        for pkg_name, _ in self.deps_build_info.dependencies:
            pkg_var = self.create_makefile_var_name_pkg(var_name, pkg_name)
            make_vars.append("$({pkg_var})".format(pkg_var=pkg_var))
        return make_vars

    def create_makefile_var_global(self, var_name, operator, values):
        make_var = [self.create_makefile_var_name_global(var_name)]
        make_var.extend(self.create_makefile_var_common(operator, values))
        return make_var

    def create_makefile_var_pkg(self, var_name, pkg_name, operator, values):
        make_var = [self.create_makefile_var_name_pkg(var_name, pkg_name)]
        make_var.extend(self.create_makefile_var_common(operator, values))
        return make_var

    def create_makefile_var_common(self, operator, values):
        return [operator, self.makefile_line_continuation, self.create_makefile_var_value(values),
                self.makefile_newline]

    @staticmethod
    def create_makefile_var_name_global(var_name):
        return "CONAN_{var}".format(var=var_name).upper()

    @staticmethod
    def create_makefile_var_name_pkg(var_name, pkg_name):
        return "CONAN_{var}_{lib}".format(var=var_name, lib=pkg_name).upper()

    def create_makefile_var_value(self, values):
        formatted_values = [value.replace("\\", "/") for value in values]
        return self.makefile_line_continuation.join(formatted_values)

    @staticmethod
    def all_dep_vars():
        return ["rootpath", "sysroot", "include_dirs", "lib_dirs", "bin_dirs", "build_dirs",
                "res_dirs", "libs", "defines", "cflags", "cxxflags", "sharedlinkflags",
                "exelinkflags", "frameworks", "framework_paths", "system_libs"]
