from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE
from conans.client.generators.cmake_common import cmake_dependency_vars,\
    cmake_macros, generate_targets_section, cmake_dependencies, cmake_package_info,\
    cmake_global_vars


class DepsCppCmake(object):
    def __init__(self, deps_cpp_info):

        def multiline(field):
            return "\n\t\t\t".join('"%s"' % p.replace("\\", "/") for p in field)

        self.include_paths = multiline(deps_cpp_info.include_paths)
        self.lib_paths = multiline(deps_cpp_info.lib_paths)
        self.res_paths = multiline(deps_cpp_info.res_paths)
        self.bin_paths = multiline(deps_cpp_info.bin_paths)
        self.build_paths = multiline(deps_cpp_info.build_paths)

        self.libs = " ".join(deps_cpp_info.libs)
        self.defines = "\n\t\t\t".join("-D%s" % d for d in deps_cpp_info.defines)
        self.compile_definitions = "\n\t\t\t".join(deps_cpp_info.defines)

        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cppflags_list = ";".join(deps_cpp_info.cppflags)
        self.cflags_list = ";".join(deps_cpp_info.cflags)
        self.sharedlinkflags_list = ";".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags_list = ";".join(deps_cpp_info.exelinkflags)

        self.rootpath = '"%s"' % deps_cpp_info.rootpath.replace("\\", "/")


class CMakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_CMAKE

    @property
    def content(self):
        sections = []

        # Per requirement variables
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = cmake_dependency_vars(dep_name, deps=deps)
            sections.append(dep_flags)

            for config, cpp_info in dep_cpp_info.configs.items():
                deps = DepsCppCmake(cpp_info)
                dep_flags = cmake_dependency_vars(dep_name, deps=deps, build_type=config)
                sections.append(dep_flags)

        # GENERAL VARIABLES
        sections.append("\n### Definition of global aggregated variables ###\n")
        sections.append(cmake_package_info(name=self.conanfile.name,
                                           version=self.conanfile.version))
        all_flags = cmake_dependencies(dependencies=self.deps_build_info.deps)
        sections.append(all_flags)
        deps = DepsCppCmake(self.deps_build_info)
        all_flags = cmake_global_vars(deps=deps)
        sections.append(all_flags)

        for config, cpp_info in self.deps_build_info.configs.items():
            deps = DepsCppCmake(cpp_info)
            dep_flags = cmake_global_vars(deps=deps, build_type=config)
            sections.append(dep_flags)

        # TARGETS
        sections.extend(generate_targets_section(self.deps_build_info.dependencies))

        # MACROS
        sections.append(cmake_macros)

        return "\n".join(sections)
