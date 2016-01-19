from conans.paths import (BUILD_INFO_GCC, BUILD_INFO_CMAKE, BUILD_INFO_QMAKE,
                          BUILD_INFO, BUILD_INFO_VISUAL_STUDIO,
                          BUILD_INFO_XCODE, BUILD_INFO_YCM)
from conans.util.files import save
import os


class Generator(object):

    def __init__(self, deps_build_info, build_info):
        self._deps_build_info = deps_build_info
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
        template_dep = ('set(CONAN_{dep}_ROOT {deps.rootpath})\n'
                        'set(CONAN_INCLUDE_DIRS_{dep} {deps.include_paths})\n'
                        'set(CONAN_LIB_DIRS_{dep} {deps.lib_paths})\n'
                        'set(CONAN_BIN_DIRS_{dep} {deps.bin_paths})\n'
                        'set(CONAN_LIBS_{dep} {deps.libs})\n'
                        'set(CONAN_DEFINES_{dep} {deps.defines})\n'
                        'set(CONAN_CXX_FLAGS_{dep} "{deps.cppflags}")\n'
                        'set(CONAN_SHARED_LINK_FLAGS_{dep} "{deps.sharedlinkflags}")\n'
                        'set(CONAN_EXE_LINKER_FLAGS_{dep} "{deps.exelinkflags}")\n'
                        'set(CONAN_C_FLAGS_{dep} "{deps.cflags}")\n')

        for dep_name, dep_cpp_info in self._deps_build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = template_dep.format(dep=dep_name.upper(),
                                            deps=deps)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self._deps_build_info)

        template = ('set(CONAN_INCLUDE_DIRS {deps.include_paths} ${{CONAN_INCLUDE_DIRS}})\n'
            'set(CONAN_LIB_DIRS {deps.lib_paths} ${{CONAN_LIB_DIRS}})\n'
            'set(CONAN_BIN_DIRS {deps.bin_paths} ${{CONAN_BIN_DIRS}})\n'
            'set(CONAN_LIBS {deps.libs} ${{CONAN_LIBS}})\n'
            'set(CONAN_DEFINES {deps.defines} ${{CONAN_DEFINES}})\n'
            'set(CONAN_CXX_FLAGS "{deps.cppflags} ${{CONAN_CXX_FLAGS}}")\n'
            'set(CONAN_SHARED_LINK_FLAGS "{deps.sharedlinkflags} ${{CONAN_SHARED_LINK_FLAGS}}")\n'
            'set(CONAN_EXE_LINKER_FLAGS "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS}}")\n'
            'set(CONAN_C_FLAGS "{deps.cflags} ${{CONAN_C_FLAGS}}")\n'
            'set(CONAN_CMAKE_MODULE_PATH {module_paths} ${{CONAN_CMAKE_MODULE_PATH}})')

        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self._deps_build_info.dependencies]
        module_paths = " ".join(rootpaths)
        all_flags = template.format(deps=deps, module_paths=module_paths)
        sections.append(all_flags)

        # MACROS
        sections.append(self._aux_cmake_test_setup())

        return "\n".join(sections)

    def _aux_cmake_test_setup(self):
        return """macro(CONAN_BASIC_SETUP)
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_flags_setup()
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})
endmacro()

macro(CONAN_FLAGS_SETUP)
    include_directories(${CONAN_INCLUDE_DIRS})
    link_directories(${CONAN_LIB_DIRS})
    add_definitions(${CONAN_DEFINES})

    # For find_library
    set(CMAKE_INCLUDE_PATH ${CONAN_INCLUDE_DIRS} ${CMAKE_INCLUDE_PATH})
    set(CMAKE_LIBRARY_PATH ${CONAN_LIB_DIRS} ${CMAKE_LIBRARY_PATH})

    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CXX_FLAGS}")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_C_FLAGS}")
    set(CMAKE_SHARED_LINK_FLAGS "${CMAKE_SHARED_LINK_FLAGS} ${CONAN_SHARED_LINK_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${CONAN_EXE_LINKER_FLAGS}")

    if(APPLE)
        # https://cmake.org/Wiki/CMake_RPATH_handling
        # CONAN GUIDE: All generated libraries should have the id and dependencies to other
        # dylibs without path, just the name, EX:
        # libMyLib1.dylib:
        #     libMyLib1.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     libMyLib0.dylib (compatibility version 0.0.0, current version 0.0.0)
        #     /usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 120.0.0)
        #     /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1197.1.1)
        set(CMAKE_SKIP_RPATH 1)  # AVOID RPATH FOR *.dylib, ALL LIBS BETWEEN THEM AND THE EXE
                                 # SHOULD BE ON THE LINKER RESOLVER PATH (./ IS ONE OF THEM)
    endif()
    if(CONAN_LINK_RUNTIME)
        string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_RELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG})
        string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_RELEASE ${CMAKE_C_FLAGS_RELEASE})
        string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_DEBUG ${CMAKE_C_FLAGS_DEBUG})
    endif()
endmacro()

macro(CONAN_OUTPUT_DIRS_SETUP)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
endmacro()

macro(CONAN_CHECK_COMPILER)
    if("${CONAN_COMPILER}" STREQUAL "Visual Studio")
        if(NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL MSVC)
            message(FATAL_ERROR "The current compiler is not MSVC")
        endif()
    elseif("${CONAN_COMPILER}" STREQUAL "gcc")
        if(NOT "${CMAKE_CXX_COMPILER_ID}" STREQUAL "GNU")
             message(FATAL_ERROR "The current compiler is not GCC")
        endif()
        string(REGEX MATCHALL "[0-9]+" GCC_VERSION_COMPONENTS ${CMAKE_CXX_COMPILER_VERSION})
        list(GET GCC_VERSION_COMPONENTS 0 GCC_MAJOR)
        list(GET GCC_VERSION_COMPONENTS 1 GCC_MINOR)
        if(NOT ${GCC_MAJOR}.${GCC_MINOR} VERSION_EQUAL "${CONAN_COMPILER_VERSION}")
           message(FATAL_ERROR "INCORRECT GCC VERSION CONAN=" ${CONAN_COMPILER_VERSION}
                               " CURRENT GCC=" ${GCC_MAJOR}.${GCC_MINOR})
        endif()
    elseif("${CONAN_COMPILER}" STREQUAL "clang")
        # TODO, CHECK COMPILER AND VERSIONS, AND MATCH WITH apple-clang TOO
    endif()

endmacro()
"""


class DepsCppQmake(object):
    def __init__(self, deps_cpp_info):
        self.include_paths = " \\\n    ".join('%s' % p.replace("\\", "/")
                                              for p in deps_cpp_info.include_paths)
        self.lib_paths = " \\\n    ".join('-L%s' % p.replace("\\", "/")
                                          for p in deps_cpp_info.lib_paths)
        self.libs = " ".join('-l%s' % l for l in deps_cpp_info.libs)
        self.defines = " \\\n    ".join('"%s"' % d for d in deps_cpp_info.defines)
        self.cppflags = " ".join(deps_cpp_info.cppflags)
        self.cflags = " ".join(deps_cpp_info.cflags)
        self.sharedlinkflags = " ".join(deps_cpp_info.sharedlinkflags)
        self.exelinkflags = " ".join(deps_cpp_info.exelinkflags)
        self.bin_paths = " \\\n    ".join('%s' % p.replace("\\", "/")
                                          for p in deps_cpp_info.bin_paths)

        self.rootpath = '%s' % deps_cpp_info.rootpath.replace("\\", "/")


class QmakeGenerator(Generator):
    @property
    def content(self):
        deps = DepsCppQmake(self._deps_build_info)

        template = ('# package{dep} \n\n'
                    'INCLUDEPATH += {deps.include_paths}\n'
                    'LIBS += {deps.lib_paths}\n'
                    'BINDIRS += {deps.bin_paths}\n'
                    'LIBS += {deps.libs}\n'
                    'DEFINES += {deps.defines}\n'
                    'QMAKE_CXXFLAGS += {deps.cppflags}\n'
                    'QMAKE_CFLAGS += {deps.cflags}\n'
                    'QMAKE_LFLAGS += {deps.sharedlinkflags}\n'
                    'QMAKE_LFLAGS += {deps.exelinkflags}\n')

        sections = []
        all_flags = template.format(dep="", deps=deps)
        sections.append(all_flags)
        template_deps = template + 'ROOTPATH{dep} = {deps.rootpath}\n\n'

        for dep_name, dep_cpp_info in self._deps_build_info.dependencies:
            deps = DepsCppQmake(dep_cpp_info)
            dep_flags = template_deps.format(dep="_" + dep_name, deps=deps)
            sections.append(dep_flags)

        return "\n".join(sections)


class GCCGenerator(Generator):

    @property
    def content(self):
        """With gcc_flags you can invoke gcc like that:
        $ gcc main.c @conanbuildinfo.gcc -o main
        """
        defines = " ".join("-D%s" % x for x in self._deps_build_info.defines)
        include_paths = " ".join("-I%s"
                                 % x.replace("\\", "/") for x in self._deps_build_info.include_paths)
        rpaths = " ".join("-Wl,-rpath=%s"
                          % x.replace("\\", "/") for x in self._deps_build_info.lib_paths)
        lib_paths = " ".join("-L%s" % x.replace("\\", "/") for x in self._deps_build_info.lib_paths)
        libs = " ".join("-l%s" % x for x in self._deps_build_info.libs)
        other_flags = " ".join(self._deps_build_info.cppflags +
                               self._deps_build_info.cflags +
                               self._deps_build_info.sharedlinkflags +
                               self._deps_build_info.exelinkflags)
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
        deps = DepsCppTXT(self._deps_build_info)

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

        for dep_name, dep_cpp_info in self._deps_build_info.dependencies:
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

    def __init__(self, deps_cpp_info, cpp_info):
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

    def __init__(self, deps_cpp_info, cpp_info):
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


class YouCompleteMeGenerator(Generator):
    template = '''
# This file is NOT licensed under the GPLv3, which is the license for the rest
# of YouCompleteMe.
#
# Here's the license text for this file:
#
# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.
#
# For more information, please refer to <http://unlicense.org/>

import os
import ycm_core
import logging


_logger = logging.getLogger(__name__)


def DirectoryOfThisScript():
  return os.path.dirname( os.path.abspath( __file__ ) )


# These are the compilation flags that will be used in case there's no
# compilation database set (by default, one is not set).
# CHANGE THIS LIST OF FLAGS. YES, THIS IS THE DROID YOU HAVE BEEN LOOKING FOR.
flags = [
{default_flags}
]


# Set this to the absolute path to the folder (NOT the file!) containing the
# compile_commands.json file to use that instead of 'flags'. See here for
# more details: http://clang.llvm.org/docs/JSONCompilationDatabase.html
#
# You can get CMake to generate this file for you by adding:
#   set( CMAKE_EXPORT_COMPILE_COMMANDS 1 )
# to your CMakeLists.txt file.
#
# Most projects will NOT need to set this to anything; you can just change the
# 'flags' list of compilation flags. Notice that YCM itself uses that approach.
compilation_database_folder = os.path.join(DirectoryOfThisScript(), 'Debug')

if os.path.exists( compilation_database_folder ):
  database = ycm_core.CompilationDatabase( compilation_database_folder )
  if not database.DatabaseSuccessfullyLoaded():
      _logger.warn("Failed to load database")
      database = None
else:
  database = None

SOURCE_EXTENSIONS = [ '.cpp', '.cxx', '.cc', '.c', '.m', '.mm' ]

def GetAbsolutePath(include_path, working_directory):
    if os.path.isabs(include_path):
        return include_path
    return os.path.join(working_directory, include_path)


def MakeRelativePathsInFlagsAbsolute( flags, working_directory ):
  if not working_directory:
    return list( flags )
  new_flags = []
  make_next_absolute = False
  path_flags = [ '-isystem', '-I', '-iquote', '--sysroot=' ]
  for flag in flags:
    new_flag = flag

    if make_next_absolute:
      make_next_absolute = False
      new_flag = GetAbsolutePath(flag, working_directory)

    for path_flag in path_flags:
      if flag == path_flag:
        make_next_absolute = True
        break

      if flag.startswith( path_flag ):
        path = flag[ len( path_flag ): ]
        new_flag = flag[:len(path_flag)] + GetAbsolutePath(path, working_directory)
        break

    if new_flag:
      new_flags.append( new_flag )
  return new_flags


def IsHeaderFile( filename ):
  extension = os.path.splitext( filename )[ 1 ]
  return extension in [ '.h', '.hxx', '.hpp', '.hh' ]


def GetCompilationInfoForFile( filename ):
  # The compilation_commands.json file generated by CMake does not have entries
  # for header files. So we do our best by asking the db for flags for a
  # corresponding source file, if any. If one exists, the flags for that file
  # should be good enough.
  if IsHeaderFile( filename ):
    basename = os.path.splitext( filename )[ 0 ]
    for extension in SOURCE_EXTENSIONS:
      replacement_file = basename + extension
      if os.path.exists( replacement_file ):
        compilation_info = database.GetCompilationInfoForFile( replacement_file )
        if compilation_info.compiler_flags_:
          return compilation_info
    return None
  return database.GetCompilationInfoForFile( filename )


def FlagsForFile( filename, **kwargs ):
  relative_to = None
  compiler_flags = None

  if database:
    # Bear in mind that compilation_info.compiler_flags_ does NOT return a
    # python list, but a "list-like" StringVec object
    compilation_info = GetCompilationInfoForFile( filename )
    if compilation_info is None:
      relative_to = DirectoryOfThisScript()
      compiler_flags = flags
    else:
      relative_to = compilation_info.compiler_working_dir_
      compiler_flags = compilation_info.compiler_flags_

  else:
    relative_to = DirectoryOfThisScript()
    compiler_flags = flags

  final_flags = MakeRelativePathsInFlagsAbsolute( compiler_flags, relative_to )
  for flag in final_flags:
      if flag.startswith("-W"):
          final_flags.remove(flag)
  _logger.info("Final flags for %s are %s" % (filename, ' '.join(final_flags)))

  return {{
    'flags': final_flags + ["-I/usr/include", "-I/usr/include/c++/5"],
    'do_cache': True
  }}
'''

    @property
    def content(self):
        def prefixed(prefix, values):
            return [prefix + x for x in values]

        flags = ['-x', 'c++']
        flags.extend(self._deps_build_info.cppflags)
        flags.extend(self._build_info.cppflags)
        flags.extend(prefixed("-D", self._deps_build_info.defines))
        flags.extend(prefixed("-D", self._build_info.defines))
        flags.extend(prefixed("-I", self._build_info.include_paths))
        flags.extend(prefixed("-I", self._deps_build_info.include_paths))

        return self.template.format(default_flags="'" + "', '".join(flags) + "'")


def write_generators(conanfile, path, output):
    """ produces auxiliary files, required to build a project or a package.
    """

    from conans.model.build_info import CppInfo

    available_generators = {"txt": (TXTGenerator, BUILD_INFO),
                            "gcc": (GCCGenerator, BUILD_INFO_GCC),
                            "cmake": (CMakeGenerator, BUILD_INFO_CMAKE),
                            "qmake": (QmakeGenerator, BUILD_INFO_QMAKE),
                            "visual_studio": (VisualStudioGenerator, BUILD_INFO_VISUAL_STUDIO),
                            "xcode": (XCodeGenerator, BUILD_INFO_XCODE),
                            "ycm": (YouCompleteMeGenerator, BUILD_INFO_YCM)}
    conanfile.cpp_info = CppInfo(path)
    conanfile.cpp_info.dependencies = []
    conanfile.package_info()

    for generator in conanfile.generators:
        if generator not in available_generators:
            output.warn("Invalid generator '%s'. Available options: %s" %
                        (generator, ", ".join(available_generators.keys())))
        else:
            generator_class, filename = available_generators[generator]
            generator = generator_class(conanfile.deps_cpp_info, conanfile.cpp_info)
            output.info("Generated %s" % filename)
            save(os.path.join(path, filename), generator.content)
