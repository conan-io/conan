from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_common import (cmake_dependencies, cmake_dependency_vars,
                                                   cmake_global_vars, cmake_macros_multi,
                                                   cmake_package_info, cmake_user_info_vars,
                                                   generate_targets_section)
from conans.model import Generator
from conans.model.build_info import CppInfo


def extend(cpp_info, config):
    """ adds the specific config configuration to the common one
    """
    config_info = cpp_info.configs.get(config)
    if config_info:
        def add_lists(seq1, seq2):
            return seq1 + [s for s in seq2 if s not in seq1]
        result = CppInfo(config_info.rootpath)
        result.includedirs = add_lists(cpp_info.includedirs, config_info.includedirs)
        result.libdirs = add_lists(cpp_info.libdirs, config_info.libdirs)
        result.bindirs = add_lists(cpp_info.bindirs, config_info.bindirs)
        result.resdirs = add_lists(cpp_info.resdirs, config_info.resdirs)
        result.builddirs = add_lists(cpp_info.builddirs, config_info.builddirs)
        result.libs = cpp_info.libs + config_info.libs
        result.defines = cpp_info.defines + config_info.defines
        result.cflags = cpp_info.cflags + config_info.cflags
        result.cxxflags = cpp_info.cxxflags + config_info.cxxflags
        result.sharedlinkflags = cpp_info.sharedlinkflags + config_info.sharedlinkflags
        result.exelinkflags = cpp_info.exelinkflags + config_info.exelinkflags
        return result
    return cpp_info


class CMakeMultiGenerator(Generator):

    @property
    def content(self):
        build_type = str(self.conanfile.settings.build_type).lower()
        result = {"conanbuildinfo_%s.cmake" % build_type: self._content_type(build_type),
                  "conanbuildinfo_multi.cmake": self._content_multi}
        return result

    @property
    def filename(self):
        pass

    def _content_type(self, build_type):
        sections = []

        # Per requirement variables
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            # Only the specific of the build_type
            dep_cpp_info = extend(dep_cpp_info, build_type)
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = cmake_dependency_vars(dep_name, deps=deps, build_type=build_type)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        sections.append("\n### Definition of global aggregated variables ###\n")
        all_flags = cmake_dependencies(dependencies=self.deps_build_info.deps,
                                       build_type=build_type)
        sections.append(all_flags)

        dep_cpp_info = extend(self.deps_build_info, build_type)
        deps = DepsCppCmake(dep_cpp_info)
        all_flags = cmake_global_vars(deps=deps, build_type=build_type)
        sections.append(all_flags)

        return "\n".join(sections)

    @property
    def _content_multi(self):
        sections = ["include(CMakeParseArguments)"]

        # USER DECLARED VARS
        sections.append("\n### Definition of user declared vars (user_info) ###\n")
        sections.append(cmake_user_info_vars(self.conanfile.deps_user_info))

        sections.append(cmake_package_info(name=self.conanfile.name,
                                           version=self.conanfile.version))

        # TARGETS
        sections.extend(generate_targets_section(self.deps_build_info.dependencies))
        # MACROS
        sections.append(cmake_macros_multi)

        return "\n".join(sections)
