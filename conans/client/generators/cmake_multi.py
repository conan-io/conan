from conans.model import Generator
from conans.client.generators.cmake_common import cmake_dependency_vars, cmake_package_info,\
    cmake_macros_multi, generate_targets_section, cmake_dependencies, cmake_global_vars
from conans.client.generators.cmake import DepsCppCmake
from conans.model.build_info import CppInfo


def extend(cpp_info, config):
    """ adds the specific config configuration to the common one
    """
    config_info = cpp_info.configs.get(config)
    if config_info:
        result = CppInfo()
        result.rootpath = config_info.rootpath
        result.includedirs = cpp_info.includedirs + config_info.includedirs
        result.libdirs = cpp_info.libdirs + config_info.libdirs
        result.bindirs = cpp_info.bindirs + config_info.bindirs
        result.resdirs = cpp_info.resdirs + config_info.resdirs
        result.builddirs = cpp_info.builddirs + config_info.builddirs
        result.libs = cpp_info.libs + config_info.libs
        result.defines = cpp_info.defines + config_info.defines
        result.cflags = cpp_info.cflags + config_info.cflags
        result.cppflags = cpp_info.cppflags + config_info.cppflags
        result.sharedlinkflags = cpp_info.sharedlinkflags + config_info.sharedlinkflags
        result.exelinkflags = cpp_info.exelinkflags + config_info.exelinkflags
        return result
    return cpp_info


class CMakeMultiGenerator(Generator):

    @property
    def content(self):
        result = {"conanbuildinfo%s.cmake" % self.build_type.lower(): self.content_type,
                  "conanbuildinfo_multi.cmake": self.content_multi}
        return result

    @property
    def filename(self):
        pass

    @property
    def content_type(self):
        sections = []

        build_type = str(self.conanfile.settings.build_type).lower()
        # Per requirement variables
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            # Only the specific of the build_type
            dep_cpp_info = extend(dep_cpp_info, build_type)
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = cmake_dependency_vars(dep_name, deps=deps, build_type=self.build_type)
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
    def content_multi(self):
        sections = []
        sections.append(cmake_package_info(name=self.conanfile.name,
                                           version=self.conanfile.version))

        # TARGETS
        template = """
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}_DEBUG}}" "${{CONAN_LIB_DIRS_{uname}_DEBUG}}"
                                  CONAN_FULLPATH_LIBS_{uname}_DEBUG)
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}_RELEASE}}" "${{CONAN_LIB_DIRS_{uname}_RELEASE}}"
                                  CONAN_FULLPATH_LIBS_{uname}_RELEASE)

    add_library({name} INTERFACE IMPORTED)
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES {deps} $<$<CONFIG:Release>:${{CONAN_FULLPATH_LIBS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_FULLPATH_LIBS_{uname}_DEBUG}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES $<$<CONFIG:Release>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_INCLUDE_DIRS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS $<$<CONFIG:Release>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_COMPILE_DEFINITIONS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS $<$<CONFIG:Release>:${{CONAN_CFLAGS_{uname}_RELEASE}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE}}>
                                                                  $<$<CONFIG:Debug>:${{CONAN_CFLAGS_{uname}_DEBUG}}  ${{CONAN_CXX_FLAGS_{uname}_DEBUG}}>)
    # set_property(TARGET {name} PROPERTY INTERFACE_LINK_FLAGS $<$<CONFIG:Release>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE}}>
    #                                                         $<$<CONFIG:Debug>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG}}  ${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG}}>)
"""
        sections.extend(generate_targets_section(template, self.deps_build_info.dependencies))
        # MACROS
        sections.append(cmake_macros_multi)

        return "\n".join(sections)
