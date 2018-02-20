from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE
from conans.client.generators.cmake_common import cmake_dependency_vars,\
    cmake_macros, generate_targets_section, cmake_dependencies, cmake_package_info,\
    cmake_global_vars, cmake_user_info_vars, cmake_settings_info


class DepsCppCmake(object):
    def __init__(self, cpp_info):
        def multiline(field):
            return "\n\t\t\t".join('"%s"' % p.replace("\\", "/") for p in field)

        self.include_paths = multiline(cpp_info.include_paths)
        self.lib_paths = multiline(cpp_info.lib_paths)
        self.res_paths = multiline(cpp_info.res_paths)
        self.bin_paths = multiline(cpp_info.bin_paths)
        self.build_paths = multiline(cpp_info.build_paths)

        self.libs = " ".join(cpp_info.libs)
        self.defines = "\n\t\t\t".join("-D%s" % d for d in cpp_info.defines)
        self.compile_definitions = "\n\t\t\t".join(cpp_info.defines)

        self.cppflags = " ".join(cpp_info.cppflags)
        self.cflags = " ".join(cpp_info.cflags)
        self.sharedlinkflags = " ".join(cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(cpp_info.exelinkflags)

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cppflags_list = ";".join(cpp_info.cppflags)
        self.cflags_list = ";".join(cpp_info.cflags)
        self.sharedlinkflags_list = ";".join(cpp_info.sharedlinkflags)
        self.exelinkflags_list = ";".join(cpp_info.exelinkflags)

        self.rootpath = '"%s"' % cpp_info.rootpath.replace("\\", "/")


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
