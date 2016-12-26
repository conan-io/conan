from conans.model import Generator
from conans.client.generators.cmake_common import cmake_single_dep_vars, cmake_multi_dep_vars,\
    cmake_macros_multi
from conans.client.generators.cmake import DepsCppCmake


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
        return "\n".join(sections)

    @property
    def content_multi(self):
        sections = []
        # TARGETS
        template = """
    conan_find_libraries_abs_path(${{CONAN_LIBS_{uname}_DEBUG}} ${{CONAN_LIB_DIRS_{uname}_DEBUG}}
                                  CONAN_FULLPATH_LIBS_{uname}_DEBUG)
    conan_find_libraries_abs_path(${{CONAN_LIBS_{uname}_RELEASE}} ${{CONAN_LIB_DIRS_{uname}_RELEASE}}
                                  CONAN_FULLPATH_LIBS_{uname}_RELEASE)

    add_library({name} INTERFACE IMPORTED)
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES {deps} $<$<CONFIG:Release>:${{CONAN_FULLPATH_LIBS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_FULLPATH_LIBS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES $<$<CONFIG:Release>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_INCLUDE_DIRS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS $<$<CONFIG:Release>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_COMPILE_DEFINITIONS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS $<$<CONFIG:Release>:${{CONAN_CFLAGS_{uname}_RELEASE}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE}}>
                                                                  $<$<CONFIG:Debug>:${{CONAN_CFLAGS_{uname}_DEBUG}}  ${{CONAN_CXX_FLAGS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_FLAGS $<$<CONFIG:Release>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE}}>
                                                             $<$<CONFIG:Debug>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG}}  ${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG}}>)
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
        return cmake_macros_multi + "\n\n" + "\n".join(sections)
