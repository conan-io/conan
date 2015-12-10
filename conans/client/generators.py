from conans.paths import (BUILD_INFO_GCC, BUILD_INFO_CMAKE, BUILD_INFO,
                          BUILD_INFO_VISUAL_STUDIO, BUILD_INFO_XCODE)
from conans.util.files import save
import os


class Generator(object):

    def __init__(self, build_info):
        self._build_info = build_info

    @property
    def content(self):
        raise NotImplementedError()


class DepsCppCmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                             for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.lib_paths)
        self.libs = " ".join(deps_cpp_info.libs)
        self.defines = "\n\t\t\t".join("-D%s" % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = "\n\t\t\t".join('"%s"' % p.replace("\\", "/")
                                         for p in deps_cpp_info.bin_paths)

        self.rootpath = '"%s"' % deps_cpp_info.rootpath.replace("\\", "/")


class CMakeGenerator(Generator):

    @property
    def content(self):
        sections = []

        # DEPS VARIABLES
        template_dep = ('SET(CONAN_{dep}_ROOT {deps.rootpath})\n'
                        'SET(CONAN_INCLUDE_DIRS_{dep} {deps.include_paths})\n'
                        'SET(CONAN_LIB_DIRS_{dep} {deps.lib_paths})\n'
                        'SET(CONAN_BIN_DIRS_{dep} {deps.bin_paths})\n'
                        'SET(CONAN_LIBS_{dep} {deps.libs})\n'
                        'SET(CONAN_DEFINES_{dep} {deps.defines})\n'
                        'SET(CONAN_CXX_FLAGS_{dep} "{deps.cppflags}")\n'
                        'SET(CONAN_SHARED_LINK_FLAGS_{dep} "{deps.sharedlinkflags}")\n'
                        'SET(CONAN_EXE_LINKER_FLAGS_{dep} "{deps.exelinkflags}")\n'
                        'SET(CONAN_C_FLAGS_{dep} "{deps.cflags}")\n')

        for dep_name, dep_cpp_info in self._build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = template_dep.format(dep=dep_name.upper(),
                                            deps=deps)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self._build_info)

        template = ('SET(CONAN_INCLUDE_DIRS {deps.include_paths} ${{CONAN_INCLUDE_DIRS}})\n'
            'SET(CONAN_LIB_DIRS {deps.lib_paths} ${{CONAN_LIB_DIRS}})\n'
            'SET(CONAN_BIN_DIRS {deps.bin_paths} ${{CONAN_BIN_DIRS}})\n'
            'SET(CONAN_LIBS {deps.libs} ${{CONAN_LIBS}})\n'
            'SET(CONAN_DEFINES {deps.defines} ${{CONAN_DEFINES}})\n'
            'SET(CONAN_CXX_FLAGS "{deps.cppflags} ${{CONAN_CXX_FLAGS}}")\n'
            'SET(CONAN_SHARED_LINK_FLAGS "{deps.sharedlinkflags} ${{CONAN_SHARED_LINK_FLAGS}}")\n'
            'SET(CONAN_EXE_LINKER_FLAGS "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS}}")\n'
            'SET(CONAN_C_FLAGS "{deps.cflags} ${{CONAN_C_FLAGS}}")\n'
            'SET(CONAN_CMAKE_MODULE_PATH {module_paths} ${{CONAN_CMAKE_MODULE_PATH}})')

        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self._build_info.dependencies]
        module_paths = " ".join(rootpaths)
        all_flags = template.format(deps=deps, module_paths=module_paths)
        sections.append(all_flags)

        # MACROS
        sections.append(self._aux_cmake_test_setup())

        return "\n".join(sections)

    def _aux_cmake_test_setup(self):
        return """MACRO(CONAN_BASIC_SETUP)
    CONAN_CHECK_COMPILER()
    CONAN_OUTPUT_DIRS_SETUP()
    CONAN_FLAGS_SETUP()
    # CMake can find findXXX.cmake files in the root of packages
    SET(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})
ENDMACRO()

MACRO(CONAN_FLAGS_SETUP)
    INCLUDE_DIRECTORIES(${CONAN_INCLUDE_DIRS})
    LINK_DIRECTORIES(${CONAN_LIB_DIRS})
    ADD_DEFINITIONS(${CONAN_DEFINES})
    SET(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CXX_FLAGS}")
    SET(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_C_FLAGS}")
    SET(CMAKE_SHARED_LINK_FLAGS "${CMAKE_SHARED_LINK_FLAGS} ${CONAN_SHARED_LINK_FLAGS}")
    SET(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${CONAN_EXE_LINKER_FLAGS}")

    IF(APPLE)
        # https://cmake.org/Wiki/CMake_RPATH_handling
        # CONAN GUIDE: All generated libraries should have the id and dependencies to other
        # dylibs without path, just the name, EX:
        # libMyLib1.dylib:
        #     libMyLib1.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     libMyLib0.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     /usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 120.0.0)
        #     /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1197.1.1)
        SET(CMAKE_SKIP_RPATH 1)  # AVOID RPATH FOR *.dylib, ALL LIBS BETWEEN THEM AND THE EXE
                                 # SHOULD BE ON THE LINKER RESOLVER PATH (./ IS ONE OF THEM)
    ENDIF()
    IF(CONAN_LINK_RUNTIME)
        STRING(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_RELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        STRING(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG})
        STRING(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_RELEASE ${CMAKE_C_FLAGS_RELEASE})
        STRING(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_DEBUG ${CMAKE_C_FLAGS_DEBUG})
    ENDIF()
ENDMACRO()

MACRO(CONAN_OUTPUT_DIRS_SETUP)
    SET(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
    SET(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
    SET(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

    SET(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
    SET(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
    SET(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
ENDMACRO()

MACRO(CONAN_CHECK_COMPILER)
    IF("${CONAN_COMPILER}" STREQUAL "Visual Studio")
        if(NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL MSVC)
            MESSAGE(FATAL_ERROR "The current compiler is not MSVC")
        endif()
    ELSEIF("${CONAN_COMPILER}" STREQUAL "gcc")
        if(NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
             MESSAGE(FATAL_ERROR "The current compiler is not GCC")
        endif()
        string(REGEX MATCHALL "[0-9]+" GCC_VERSION_COMPONENTS ${CMAKE_CXX_COMPILER_VERSION})
        list(GET GCC_VERSION_COMPONENTS 0 GCC_MAJOR)
        list(GET GCC_VERSION_COMPONENTS 1 GCC_MINOR)
        if(NOT ${GCC_MAJOR}.${GCC_MINOR} VERSION_EQUAL "${CONAN_COMPILER_VERSION}")
           message(FATAL_ERROR "INCORRECT GCC VERSION CONAN=" ${CONAN_COMPILER_VERSION}
                               " CURRENT GCC=" ${GCC_MAJOR}.${GCC_MINOR})
        endif()
    ELSEIF("${CONAN_COMPILER}" STREQUAL "clang")
        # TODO, CHECK COMPILER AND VERSIONS, AND MATCH WITH apple-clang TOO
    endif()

ENDMACRO()
"""


class GCCGenerator(Generator):

    @property
    def content(self):
        """With gcc_flags you can invoke gcc like that:
        $ gcc main.c @conanbuildinfo.gcc -o main
        """
        defines = " ".join("-D%s" % x for x in self._build_info.defines)
        include_paths = " ".join("-I%s"
                                 % x.replace("\\", "/") for x in self._build_info.include_paths)
        rpaths = " ".join("-Wl,-rpath=%s"
                          % x.replace("\\", "/") for x in self._build_info.lib_paths)
        lib_paths = " ".join("-L%s" % x.replace("\\", "/") for x in self._build_info.lib_paths)
        libs = " ".join("-l%s" % x for x in self._build_info.libs)
        other_flags = " ".join(self._build_info.cppflags +
                               self._build_info.cflags +
                               self._build_info.sharedlinkflags +
                               self._build_info.exelinkflags)
        flags = ("%s %s %s %s %s %s"
                 % (defines, include_paths, lib_paths, rpaths, libs, other_flags))
        return flags


class DepsCppTXT(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = "\n".join(p.replace("\\", "/")
                                       for p in deps_cpp_info.include_paths)
        self.lib_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.lib_paths)
        self.libs = "\n".join(deps_cpp_info.libs)
        self.defines = "\n".join(deps_cpp_info.defines)
        self.cppflags = "\n".join(deps_cpp_info.cppflags)
        self.cflags = "\n".join(deps_cpp_info.cflags)
        self.sharedlinkflags = "\n".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = "\n".join(deps_cpp_info.exelinkflags)
        self.bin_paths = "\n".join(p.replace("\\", "/")
                                   for p in deps_cpp_info.bin_paths)
        self.rootpath = "%s" % deps_cpp_info.rootpath.replace("\\", "/")


class TXTGenerator(Generator):

    @property
    def content(self):
        deps = DepsCppTXT(self._build_info)

        template = ('[includedirs{dep}]\n{deps.include_paths}\n\n'
                    '[libdirs{dep}]\n{deps.lib_paths}\n\n'
                    '[bindirs{dep}]\n{deps.bin_paths}\n\n'
                    '[libs{dep}]\n{deps.libs}\n\n'
                    '[defines{dep}]\n{deps.defines}\n\n'
                    '[cppflags{dep}]\n{deps.cppflags}\n\n'
                    '[cflags{dep}]\n{deps.cflags}\n\n'
                    '[sharedlinkflags{dep}]\n{deps.sharedlinkflags}\n\n'
                    '[exelinkflags{dep}]\n{deps.exelinkflags}\n\n')

        sections = []
        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        template_deps = template + '[rootpath{dep}]\n{deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self._build_info.dependencies:
            deps = DepsCppTXT(dep_cpp_info)
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            sections.append(dep_flags)

        return "\n".join(sections)


class VisualStudioGenerator(Generator):

    template = '''<?xml version="1.0" encoding="utf-8"?>
<Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
  <ImportGroup Label="PropertySheets" />
  <PropertyGroup Label="UserMacros" />
  <PropertyGroup />
  <ItemDefinitionGroup>
    <ClCompile>
      <AdditionalIncludeDirectories>{include_dirs}%(AdditionalIncludeDirectories)</AdditionalIncludeDirectories>
      <PreprocessorDefinitions>{definitions}%(PreprocessorDefinitions)</PreprocessorDefinitions>
      <AdditionalOptions>{compiler_flags} %(AdditionalOptions)</AdditionalOptions>
    </ClCompile>
    <Link>
      <AdditionalLibraryDirectories>{lib_dirs}%(AdditionalLibraryDirectories)</AdditionalLibraryDirectories>
      <AdditionalDependencies>{libs}%(AdditionalDependencies)</AdditionalDependencies>
      <AdditionalOptions>{linker_flags} %(AdditionalOptions)</AdditionalOptions>
    </Link>
  </ItemDefinitionGroup>
  <ItemGroup />
</Project>'''

    def __init__(self, deps_cpp_info):
        self.include_dirs = "".join('%s;' % p.replace("\\", "/")
                                    for p in deps_cpp_info.include_paths)
        self.lib_dirs = "".join('%s;' % p.replace("\\", "/")
                                for p in deps_cpp_info.lib_paths)
        self.libs = "".join(['%s.lib;' % lib if not lib.endswith(".lib")
                             else '%s;' % lib for lib in deps_cpp_info.libs])
        self.definitions = "".join("%s;" % d for d in deps_cpp_info.defines)
        self.compiler_flags = " ".join(deps_cpp_info.cppflags + deps_cpp_info.cflags)
        self.linker_flags = " ".join(deps_cpp_info.sharedlinkflags)

    @property
    def content(self):
        return self.template.format(**self.__dict__)


class XCodeGenerator(Generator):

    template = '''
HEADER_SEARCH_PATHS = $(inherited) {include_dirs}
LIBRARY_SEARCH_PATHS = $(inherited) {lib_dirs}
OTHER_LDFLAGS = $(inherited) {linker_flags} {libs}

GCC_PREPROCESSOR_DEFINITIONS = $(inherited) {compiler_flags}
OTHER_CFLAGS = $(inherited)
OTHER_CPLUSPLUSFLAGS = $(inherited)
'''

    def __init__(self, deps_cpp_info):
        self.include_dirs = " ".join('"%s"' % p.replace("\\", "/")
                                     for p in deps_cpp_info.include_paths)
        self.lib_dirs = " ".join('"%s"' % p.replace("\\", "/")
                                 for p in deps_cpp_info.lib_paths)
        self.libs = " ".join(['-l%s' % lib for lib in deps_cpp_info.libs])
        self.definitions = " ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.compiler_flags = " ".join(deps_cpp_info.cppflags + deps_cpp_info.cflags)
        self.linker_flags = " ".join(deps_cpp_info.sharedlinkflags)

    @property
    def content(self):
        return self.template.format(**self.__dict__)


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """
    available_generators = {"txt": (TXTGenerator, BUILD_INFO),
                            "gcc": (GCCGenerator, BUILD_INFO_GCC),
                            "cmake": (CMakeGenerator, BUILD_INFO_CMAKE),
                            "visual_studio": (VisualStudioGenerator, BUILD_INFO_VISUAL_STUDIO),
                            "xcode": (XCodeGenerator, BUILD_INFO_XCODE)}

    for generator in conanfile.generators:
        if generator not in available_generators:
            output.warn("Invalid generator '%s'. Available options: %s" %
                        (generator, ", ".join(available_generators.keys())))
        else:
            generator_class, filename = available_generators[generator]
            generator = generator_class(conanfile.deps_cpp_info)
            output.info("Generated %s" % filename)
            save(os.path.join(path, filename), generator.content)
