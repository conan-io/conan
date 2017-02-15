from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE
from conans.client.generators.cmake_common import cmake_single_dep_vars, cmake_multi_dep_vars,\
    cmake_macros, generate_targets_section


class DepsCppCmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                             for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.lib_paths)
        self.libs = " ".join(deps_cpp_info.libs)

        self.defines = "\n\t\t\t".join("-D%s" % d for d in deps_cpp_info.defines)
        self.compile_definitions = "\n\t\t\t".join(deps_cpp_info.defines)

        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.bin_paths)

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
            dep_flags = cmake_single_dep_vars(dep_name, deps=deps)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self.deps_build_info)
        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self.deps_build_info.dependencies]
        all_flags = cmake_multi_dep_vars(deps=deps, root_paths=rootpaths,
                                         dependencies=self.deps_build_info.deps,
                                         name=self.conanfile.name, version=self.conanfile.version)

        sections.append("\n### Definition of global aggregated variables ###\n")
        sections.append(all_flags)

        # TARGETS
        template = """
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}}}" "${{CONAN_LIB_DIRS_{uname}}}"
                                  CONAN_FULLPATH_LIBS_{uname})

    add_library({name} INTERFACE IMPORTED)
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES ${{CONAN_FULLPATH_LIBS_{uname}}} {deps} ${{CONAN_SHARED_LINKER_FLAGS_{uname}}} ${{CONAN_EXE_LINKER_FLAGS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES ${{CONAN_INCLUDE_DIRS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{CONAN_COMPILE_DEFINITIONS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS ${{CONAN_CFLAGS_{uname}}} ${{CONAN_CXX_FLAGS_{uname}}})
    # Not working
    # set_property(TARGET {name} PROPERTY INTERFACE_LINK_FLAGS ${{CONAN_SHARED_LINKER_FLAGS_{uname}}} ${{CONAN_EXE_LINKER_FLAGS_{uname}}})
"""
        sections.extend(generate_targets_section(template, self.deps_build_info.dependencies))

        # MACROS
        sections.append(cmake_macros)

        return "\n".join(sections)
