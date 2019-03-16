from conans.client.generators.cmake_common import cmake_dependencies, cmake_dependency_vars, \
    cmake_global_vars, cmake_macros, cmake_package_info, cmake_settings_info, cmake_user_info_vars, \
    generate_targets_section
from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE


class DepsCppCmake(object):
    def __init__(self, cpp_info):
        def join_paths(paths):
            # Paths are doubled quoted, and escaped (but spaces)
            return "\n\t\t\t".join('"%s"'
                                   % p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
                                   for p in paths)

        def join_flags(separator, values):
            # Flags have to be escaped
            return separator.join(v.replace('\\', '\\\\').replace('$', '\\$').replace('"', '\\"')
                                  for v in values)

        def join_defines(values, prefix=""):
            # Defines have to be escaped, included spaces
            return "\n\t\t\t".join('"%s%s"' % (prefix, v.replace('\\', '\\\\').replace('$', '\\$').
                                   replace('"', '\\"'))
                                   for v in values)

        self.include_paths = join_paths(cpp_info.include_paths)
        self.lib_paths = join_paths(cpp_info.lib_paths)
        self.res_paths = join_paths(cpp_info.res_paths)
        self.bin_paths = join_paths(cpp_info.bin_paths)
        self.build_paths = join_paths(cpp_info.build_paths)
        self.src_paths = join_paths(cpp_info.src_paths)

        self.libs = join_flags(" ", cpp_info.libs)
        self.defines = join_defines(cpp_info.defines, "-D")
        self.compile_definitions = join_defines(cpp_info.defines)

        self.cxxflags = join_flags(" ", cpp_info.cxxflags)
        self.cflags = join_flags(" ", cpp_info.cflags)
        self.sharedlinkflags = join_flags(" ", cpp_info.sharedlinkflags)
        self.exelinkflags = join_flags(" ", cpp_info.exelinkflags)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cxxflags_list = join_flags(";", cpp_info.cxxflags)
        self.cflags_list = join_flags(";", cpp_info.cflags)
        self.sharedlinkflags_list = join_flags(";", cpp_info.sharedlinkflags)
        self.exelinkflags_list = join_flags(";", cpp_info.exelinkflags)

        self.rootpath = join_paths([cpp_info.rootpath])


class CMakeGenerator(Generator):
    @property
    def filename(self):
        return BUILD_INFO_CMAKE

    @property
    def content(self):
        sections = ["include(CMakeParseArguments)"]

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
        sections.append(cmake_settings_info(self.conanfile.settings))
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

        # USER DECLARED VARS
        sections.append("\n### Definition of user declared vars (user_info) ###\n")
        sections.append(cmake_user_info_vars(self.conanfile.deps_user_info))

        return "\n".join(sections)
