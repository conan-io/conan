from conans.model import Generator
from conans.paths import BUILD_INFO_CMAKE


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

        # DEPS VARIABLES
        template_dep = ('set(CONAN_{dep}_ROOT {deps.rootpath})\n'
                        'set(CONAN_INCLUDE_DIRS_{dep} {deps.include_paths})\n'
                        'set(CONAN_LIB_DIRS_{dep} {deps.lib_paths})\n'
                        'set(CONAN_BIN_DIRS_{dep} {deps.bin_paths})\n'
                        'set(CONAN_LIBS_{dep} {deps.libs})\n'
                        'set(CONAN_DEFINES_{dep} {deps.defines})\n'
                        '# COMPILE_DEFINITIONS are equal to CONAN_DEFINES without -D, for targets\n'
                        'set(CONAN_COMPILE_DEFINITIONS_{dep} {deps.compile_definitions})\n'
                        'set(CONAN_CXX_FLAGS_{dep} "{deps.cppflags}")\n'
                        'set(CONAN_SHARED_LINKER_FLAGS_{dep} "{deps.sharedlinkflags}")\n'
                        'set(CONAN_EXE_LINKER_FLAGS_{dep} "{deps.exelinkflags}")\n'
                        'set(CONAN_C_FLAGS_{dep} "{deps.cflags}")\n')

        for dep_name, dep_cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppCmake(dep_cpp_info)
            dep_flags = template_dep.format(dep=dep_name.upper(), deps=deps)
            sections.append(dep_flags)

        # GENERAL VARIABLES
        deps = DepsCppCmake(self.deps_build_info)

        template = ('set(CONAN_PACKAGE_NAME {name})\n'
                    'set(CONAN_PACKAGE_VERSION {version})\n'
                    'set(CONAN_DEPENDENCIES {dependencies})\n'
                    'set(CONAN_INCLUDE_DIRS {deps.include_paths} ${{CONAN_INCLUDE_DIRS}})\n'
                    'set(CONAN_LIB_DIRS {deps.lib_paths} ${{CONAN_LIB_DIRS}})\n'
                    'set(CONAN_BIN_DIRS {deps.bin_paths} ${{CONAN_BIN_DIRS}})\n'
                    'set(CONAN_LIBS {deps.libs} ${{CONAN_LIBS}})\n'
                    'set(CONAN_DEFINES {deps.defines} ${{CONAN_DEFINES}})\n'
                    'set(CONAN_CXX_FLAGS "{deps.cppflags} ${{CONAN_CXX_FLAGS}}")\n'
                    'set(CONAN_SHARED_LINKER_FLAGS "{deps.sharedlinkflags} ${{CONAN_SHARED_LINKER_FLAGS}}")\n'
                    'set(CONAN_EXE_LINKER_FLAGS "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS}}")\n'
                    'set(CONAN_C_FLAGS "{deps.cflags} ${{CONAN_C_FLAGS}}")\n'
                    'set(CONAN_CMAKE_MODULE_PATH {module_paths} ${{CONAN_CMAKE_MODULE_PATH}})')

        rootpaths = [DepsCppCmake(dep_cpp_info).rootpath for _, dep_cpp_info
                     in self.deps_build_info.dependencies]
        module_paths = " ".join(rootpaths)
        all_flags = template.format(deps=deps, module_paths=module_paths,
                                    dependencies=" ".join(self.deps_build_info.deps),
                                    name=self.conanfile.name, version=self.conanfile.version)

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

        # MACROS
        sections.append(self._aux_cmake_test_setup())

        return "\n".join(sections)

    def _aux_cmake_test_setup(self):
        return """macro(conan_basic_setup)
    conan_check_compiler()
    conan_output_dirs_setup()
    conan_set_find_library_paths()
    if(NOT "${ARGV0}" STREQUAL "TARGETS")
        message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()
    conan_set_rpath()
    conan_set_vs_runtime()
    conan_set_libcxx()
    conan_set_find_paths()
endmacro()

macro(conan_set_find_paths)
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})
endmacro()

macro(conan_set_find_library_paths)
    # For find_library
    set(CMAKE_INCLUDE_PATH ${CONAN_INCLUDE_DIRS} ${CMAKE_INCLUDE_PATH})
    set(CMAKE_LIBRARY_PATH ${CONAN_LIB_DIRS} ${CMAKE_LIBRARY_PATH})
endmacro()

macro(conan_set_vs_runtime)
    if(CONAN_LINK_RUNTIME)
        if(DEFINED CMAKE_CXX_FLAGS_RELEASE)
            string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_RELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        endif()
        if(DEFINED CMAKE_CXX_FLAGS_DEBUG)
            string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG})
        endif()
        if(DEFINED CMAKE_C_FLAGS_RELEASE)
            string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_RELEASE ${CMAKE_C_FLAGS_RELEASE})
        endif()
        if(DEFINED CMAKE_C_FLAGS_DEBUG)
            string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} CMAKE_C_FLAGS_DEBUG ${CMAKE_C_FLAGS_DEBUG})
        endif()
    endif()
endmacro()

macro(conan_set_libcxx)
    if(DEFINED CONAN_LIBCXX)
        message(STATUS "Conan C++ stdlib: ${CONAN_LIBCXX}")
        if(CONAN_COMPILER STREQUAL "clang" OR CONAN_COMPILER STREQUAL "apple-clang")
            if(CONAN_LIBCXX STREQUAL "libstdc++" OR CONAN_LIBCXX STREQUAL "libstdc++11" )
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -stdlib=libstdc++")
            elseif(CONAN_LIBCXX STREQUAL "libc++")
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -stdlib=libc++")
            endif()
        endif()
        if(CONAN_LIBCXX STREQUAL "libstdc++11")
            add_definitions(-D_GLIBCXX_USE_CXX11_ABI=1)
        elseif(CONAN_LIBCXX STREQUAL "libstdc++")
            add_definitions(-D_GLIBCXX_USE_CXX11_ABI=0)
        endif()
    endif()
endmacro()

macro(conan_set_rpath)
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
endmacro()


macro(conan_global_flags)
    if(CONAN_SYSTEM_INCLUDES)
        include_directories(SYSTEM ${CONAN_INCLUDE_DIRS})
    else()
        include_directories(${CONAN_INCLUDE_DIRS})
    endif()
    link_directories(${CONAN_LIB_DIRS})
    add_definitions(${CONAN_DEFINES})

    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CXX_FLAGS}")
    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_C_FLAGS}")
    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${CONAN_SHARED_LINKER_FLAGS}")
    set(CMAKE_EXE_LINKER_FLAGS "${CMAKE_EXE_LINKER_FLAGS} ${CONAN_EXE_LINKER_FLAGS}")
endmacro()

macro(conan_flags_setup)
    # Macro maintained for backwards compatibility
    conan_set_find_library_paths()
    conan_global_flags()
    conan_set_rpath()
    conan_set_vs_runtime()
    conan_set_libcxx()
endmacro()

macro(conan_output_dirs_setup)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
    set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
    set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
endmacro()

macro(conan_split_version VERSION_STRING MAJOR MINOR)
    #make a list from the version string
    string(REPLACE "." ";" VERSION_LIST ${${VERSION_STRING}})

    #write output values
    list(GET VERSION_LIST 0 ${MAJOR})
    list(GET VERSION_LIST 1 ${MINOR})
endmacro()

macro(conan_error_compiler_version)
    message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}' version 'compiler.version=${CONAN_COMPILER_VERSION}'"
                        " is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}=" ${VERSION_MAJOR}.${VERSION_MINOR}')
endmacro()

set(_CONAN_CURRENT_DIR ${CMAKE_CURRENT_LIST_DIR})
function(conan_get_compiler CONAN_INFO_COMPILER CONAN_INFO_COMPILER_VERSION)
    MESSAGE(STATUS "Current conanbuildinfo.cmake directory: " ${_CONAN_CURRENT_DIR})
    if(NOT EXISTS ${_CONAN_CURRENT_DIR}/conaninfo.txt)
        message(STATUS "WARN: conaninfo.txt not found")
        return()
    endif()

    file (READ "${_CONAN_CURRENT_DIR}/conaninfo.txt" CONANINFO)

    string(REGEX MATCH "compiler=([A-Za-z0-9_ ]+)" _MATCHED ${CONANINFO})
    if(DEFINED CMAKE_MATCH_1)
        string(STRIP ${CMAKE_MATCH_1} _CONAN_INFO_COMPILER)
        set(${CONAN_INFO_COMPILER} ${_CONAN_INFO_COMPILER} PARENT_SCOPE)
    endif()

    string(REGEX MATCH "compiler.version=([-A-Za-z0-9_.]+)" _MATCHED ${CONANINFO})
    if(DEFINED CMAKE_MATCH_1)
        string(STRIP ${CMAKE_MATCH_1} _CONAN_INFO_COMPILER_VERSION)
        set(${CONAN_INFO_COMPILER_VERSION} ${_CONAN_INFO_COMPILER_VERSION} PARENT_SCOPE)
    endif()
endfunction()

function(check_compiler_version)
    CONAN_SPLIT_VERSION(CMAKE_CXX_COMPILER_VERSION VERSION_MAJOR VERSION_MINOR)
    if(CMAKE_CXX_COMPILER_ID MATCHES MSVC)
        # https://cmake.org/cmake/help/v3.2/variable/MSVC_VERSION.html
        if( (CONAN_COMPILER_VERSION STREQUAL "14" AND NOT VERSION_MAJOR STREQUAL "19") OR
            (CONAN_COMPILER_VERSION STREQUAL "12" AND NOT VERSION_MAJOR STREQUAL "18") OR
            (CONAN_COMPILER_VERSION STREQUAL "11" AND NOT VERSION_MAJOR STREQUAL "17") OR
            (CONAN_COMPILER_VERSION STREQUAL "10" AND NOT VERSION_MAJOR STREQUAL "16") OR
            (CONAN_COMPILER_VERSION STREQUAL "9" AND NOT VERSION_MAJOR STREQUAL "15") OR
            (CONAN_COMPILER_VERSION STREQUAL "8" AND NOT VERSION_MAJOR STREQUAL "14") OR
            (CONAN_COMPILER_VERSION STREQUAL "7" AND NOT VERSION_MAJOR STREQUAL "13") OR
            (CONAN_COMPILER_VERSION STREQUAL "6" AND NOT VERSION_MAJOR STREQUAL "12") )
            conan_error_compiler_version()
        endif()
    elseif(CONAN_COMPILER STREQUAL "gcc" OR CONAN_COMPILER MATCHES "clang")
        if(NOT ${VERSION_MAJOR}.${VERSION_MINOR} VERSION_EQUAL CONAN_COMPILER_VERSION)
           conan_error_compiler_version()
        endif()
    else()
        message("Skipping version checking of not detected compiler...")
    endif()
endfunction()

function(conan_check_compiler)
    if(NOT DEFINED CMAKE_CXX_COMPILER_ID)
        if(DEFINED CMAKE_C_COMPILER_ID)
            message(STATUS "This project seems to be plain C, using '${CMAKE_C_COMPILER_ID}' compiler")
            set(CMAKE_CXX_COMPILER_ID ${CMAKE_C_COMPILER_ID})
            set(CMAKE_CXX_COMPILER_VERSION ${CMAKE_C_COMPILER_VERSION})
        else()
            message(FATAL_ERROR "This project seems to be plain C, but no compiler defined")
        endif()
    endif()
    if(CONAN_DISABLE_CHECK_COMPILER)
        message(STATUS "WARN: Disabled conan compiler checks")
        return()
    endif()

    if(NOT DEFINED CONAN_COMPILER)
        conan_get_compiler(CONAN_COMPILER CONAN_COMPILER_VERSION)
        if(NOT DEFINED CONAN_COMPILER)
            message(STATUS "WARN: CONAN_COMPILER variable not set, please make sure yourself that "
                       "your compiler and version matches your declared settings")
            return()
        endif()
    endif()

    if( (CONAN_COMPILER STREQUAL "Visual Studio" AND NOT CMAKE_CXX_COMPILER_ID MATCHES MSVC) OR
        (CONAN_COMPILER STREQUAL "gcc" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU") OR
        (CONAN_COMPILER STREQUAL "apple-clang" AND (NOT APPLE OR NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")) OR
        (CONAN_COMPILER STREQUAL "clang" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang") )

        message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}', is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}'")
    endif()

    if(NOT DEFINED CONAN_COMPILER_VERSION)
        message(STATUS "WARN: CONAN_COMPILER_VERSION variable not set, please make sure yourself "
                       "that your compiler version matches your declared settings")
        return()
    endif()
    check_compiler_version()
endfunction()
"""
