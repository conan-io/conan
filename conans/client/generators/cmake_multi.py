from conans.model import Generator
from conans.client.generators.cmake_common import cmake_single_dep_vars, cmake_multi_dep_vars,\
    cmake_macros_multi


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


class CMakeMultiGenerator(Generator):
    @property
    def build_type(self):
        return "_" + str(self.conanfile.settings.build_type).upper()

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

        # Per requirement variables
        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = cmake_single_dep_vars(dep_name, deps=deps, build_type=self.build_type)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self.deps_build_info)
        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self.deps_build_info.dependencies]
        all_flags = cmake_multi_dep_vars(deps=deps, root_paths=rootpaths,
                                         dependencies=self.deps_build_info.deps,
                                         name=self.conanfile.name, version=self.conanfile.version,
                                         build_type=self.build_type)

        sections.append("\n### Definition of global aggregated variables ###\n")
        sections.append(all_flags)

        # TARGETS
        template = """
    foreach(_LIBRARY_NAME ${{CONAN_LIBS_{uname}}})
        unset(FOUND_LIBRARY CACHE)
        find_library(FOUND_LIBRARY NAME ${{_LIBRARY_NAME}} PATHS ${{CONAN_LIB_DIRS_{uname}}} NO_DEFAULT_PATH)
        if(FOUND_LIBRARY)
            set(CONAN_FULLPATH_LIBS_{uname} ${{CONAN_FULLPATH_LIBS_{uname}}} ${{FOUND_LIBRARY}})
        else()
            message(STATUS "Library ${{_LIBRARY_NAME}} not found in package, might be system one")
            set(CONAN_FULLPATH_LIBS_{uname} ${{CONAN_FULLPATH_LIBS_{uname}}} ${{_LIBRARY_NAME}})
        endif()
    endforeach()

    add_library({name} INTERFACE IMPORTED)
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES ${{CONAN_FULLPATH_LIBS_{uname}}} {deps})
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES ${{CONAN_INCLUDE_DIRS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{CONAN_COMPILE_DEFINITIONS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS ${{CONAN_CFLAGS_{uname}}} ${{CONAN_CXX_FLAGS_{uname}}})
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_FLAGS ${{CONAN_SHARED_LINKER_FLAGS_{uname}}} ${{CONAN_EXE_LINKER_FLAGS_{uname}}})
"""
        existing_deps = self.deps_build_info.deps

        sections.append("\n###  Definition of macros and functions ###\n")
        sections.append('macro(conan_define_targets)\n'
                        '    if(${CMAKE_VERSION} VERSION_LESS "3.1.2")\n'
                        '        message(FATAL_ERROR "TARGETS not supported by your CMake version!")\n'
                        '    endif()  # CMAKE > 3.x\n')

        for dep_name, dep_info in self.deps_build_info.dependencies:
            use_deps = ["CONAN_PKG::%s" % d for d in dep_info.deps if d in existing_deps]
            deps = "" if not use_deps else " ".join(use_deps)
            sections.append(template.format(name="CONAN_PKG::%s" % dep_name, deps=deps,
                                            uname=dep_name.upper()))

        sections.append('endmacro()\n')

        return "\n".join(sections)

    @property
    def content_multi(self):
        return cmake_macros_multi
