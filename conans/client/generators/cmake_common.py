_cmake_single_dep_vars = """set(CONAN_{dep}_ROOT{build_type} {deps.rootpath})
set(CONAN_INCLUDE_DIRS_{dep}{build_type} {deps.include_paths})
set(CONAN_LIB_DIRS_{dep}{build_type} {deps.lib_paths})
set(CONAN_BIN_DIRS_{dep}{build_type} {deps.bin_paths})
set(CONAN_RES_DIRS_{dep}{build_type} {deps.res_paths})
set(CONAN_BUILD_DIRS_{dep}{build_type} {deps.build_paths})
set(CONAN_LIBS_{dep}{build_type} {deps.libs})
set(CONAN_DEFINES_{dep}{build_type} {deps.defines})
# COMPILE_DEFINITIONS are equal to CONAN_DEFINES without -D, for targets
set(CONAN_COMPILE_DEFINITIONS_{dep}{build_type} {deps.compile_definitions})

set(CONAN_C_FLAGS_{dep}{build_type} "{deps.cflags}")
set(CONAN_CXX_FLAGS_{dep}{build_type} "{deps.cppflags}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type} "{deps.sharedlinkflags}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type} "{deps.exelinkflags}")

# For modern cmake targets we use the list variables (separated with ;)
set(CONAN_C_FLAGS_{dep}{build_type}_LIST "{deps.cflags_list}")
set(CONAN_CXX_FLAGS_{dep}{build_type}_LIST "{deps.cppflags_list}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.sharedlinkflags_list}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.exelinkflags_list}")

"""


def _build_type_str(build_type):
    if build_type:
        return "_" + str(build_type).upper()
    return ""


def cmake_dependency_vars(name, deps, build_type=""):
    build_type = _build_type_str(build_type)
    return _cmake_single_dep_vars.format(dep=name.upper(), deps=deps, build_type=build_type)


_cmake_package_info = """set(CONAN_PACKAGE_NAME {name})
set(CONAN_PACKAGE_VERSION {version})
"""


def cmake_package_info(name, version):
    return _cmake_package_info.format(name=name, version=version)


def cmake_dependencies(dependencies, build_type=""):
    build_type = _build_type_str(build_type)
    dependencies = " ".join(dependencies)
    return "set(CONAN_DEPENDENCIES{build_type} {dependencies})".format(dependencies=dependencies,
                                                                       build_type=build_type)


_cmake_multi_dep_vars = """{cmd_line_args}
set(CONAN_INCLUDE_DIRS{build_type} {deps.include_paths} ${{CONAN_INCLUDE_DIRS{build_type}}})
set(CONAN_LIB_DIRS{build_type} {deps.lib_paths} ${{CONAN_LIB_DIRS{build_type}}})
set(CONAN_BIN_DIRS{build_type} {deps.bin_paths} ${{CONAN_BIN_DIRS{build_type}}})
set(CONAN_RES_DIRS{build_type} {deps.res_paths} ${{CONAN_RES_DIRS{build_type}}})
set(CONAN_LIBS{build_type} {deps.libs} ${{CONAN_LIBS{build_type}}})
set(CONAN_DEFINES{build_type} {deps.defines} ${{CONAN_DEFINES{build_type}}})
set(CONAN_CMAKE_MODULE_PATH{build_type} {deps.build_paths} ${{CONAN_CMAKE_MODULE_PATH{build_type}}})

set(CONAN_CXX_FLAGS{build_type} "{deps.cppflags} ${{CONAN_CXX_FLAGS{build_type}}}")
set(CONAN_SHARED_LINKER_FLAGS{build_type} "{deps.sharedlinkflags} ${{CONAN_SHARED_LINKER_FLAGS{build_type}}}")
set(CONAN_EXE_LINKER_FLAGS{build_type} "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS{build_type}}}")
set(CONAN_C_FLAGS{build_type} "{deps.cflags} ${{CONAN_C_FLAGS{build_type}}}")
"""


def cmake_global_vars(deps, build_type=""):
    if not build_type:
        cmd_line_args = """# Storing original command line args (CMake helper) flags
set(CONAN_CMD_CXX_FLAGS ${CONAN_CXX_FLAGS})

set(CONAN_CMD_SHARED_LINKER_FLAGS ${CONAN_SHARED_LINKER_FLAGS})
set(CONAN_CMD_C_FLAGS ${CONAN_C_FLAGS})
# Defining accumulated conan variables for all deps
"""
    else:
        cmd_line_args = ""
    return _cmake_multi_dep_vars.format(cmd_line_args=cmd_line_args,
                                        deps=deps, build_type=_build_type_str(build_type))

_target_template = """
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}}}" "${{CONAN_LIB_DIRS_{uname}}}"
                                  CONAN_FULLPATH_LIBS_{uname})
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}_DEBUG}}" "${{CONAN_LIB_DIRS_{uname}_DEBUG}}"
                                  CONAN_FULLPATH_LIBS_{uname}_DEBUG)
    conan_find_libraries_abs_path("${{CONAN_LIBS_{uname}_RELEASE}}" "${{CONAN_LIB_DIRS_{uname}_RELEASE}}"
                                  CONAN_FULLPATH_LIBS_{uname}_RELEASE)

    add_library({name} INTERFACE IMPORTED)

    # Property INTERFACE_LINK_FLAGS do not work, necessary to add to INTERFACE_LINK_LIBRARIES
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES ${{CONAN_FULLPATH_LIBS_{uname}}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_LIST}}
                                                                 $<$<CONFIG:Release>:${{CONAN_FULLPATH_LIBS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:RelWithDebInfo>:${{CONAN_FULLPATH_LIBS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:MinSizeRel>:${{CONAN_FULLPATH_LIBS_{uname}_RELEASE}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<CONFIG:Debug>:${{CONAN_FULLPATH_LIBS_{uname}_DEBUG}} ${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG_LIST}} ${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG_LIST}}>
                                                                 {deps})
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES ${{CONAN_INCLUDE_DIRS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_INCLUDE_DIRS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{CONAN_COMPILE_DEFINITIONS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_COMPILE_DEFINITIONS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS ${{CONAN_C_FLAGS_{uname}_LIST}} ${{CONAN_CXX_FLAGS_{uname}_LIST}}
                                                                  $<$<CONFIG:Release>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:RelWithDebInfo>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:MinSizeRel>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:Debug>:${{CONAN_C_FLAGS_{uname}_DEBUG_LIST}}  ${{CONAN_CXX_FLAGS_{uname}_DEBUG_LIST}}>)
 """


def generate_targets_section(dependencies):
    section = []
    section.append("\n###  Definition of macros and functions ###\n")
    section.append('macro(conan_define_targets)\n'
                   '    if(${CMAKE_VERSION} VERSION_LESS "3.1.2")\n'
                   '        message(FATAL_ERROR "TARGETS not supported by your CMake version!")\n'
                   '    endif()  # CMAKE > 3.x\n'
                   '    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CMD_CXX_FLAGS}")\n'
                   '    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_CMD_C_FLAGS}")\n'
                   '    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${CONAN_CMD_SHARED_LINKER_FLAGS}")\n')

    for dep_name, dep_info in dependencies:
        use_deps = ["CONAN_PKG::%s" % d for d in dep_info.public_deps]
        deps = "" if not use_deps else " ".join(use_deps)
        section.append(_target_template.format(name="CONAN_PKG::%s" % dep_name, deps=deps,
                                               uname=dep_name.upper()))

    all_targets = " ".join(["CONAN_PKG::%s" % name for name, _ in dependencies])
    section.append('    set(CONAN_TARGETS %s)\n' % all_targets)
    section.append('endmacro()\n')
    return section


_cmake_common_macros = """

function(conan_find_libraries_abs_path libraries package_libdir libraries_abs_path)
    foreach(_LIBRARY_NAME ${libraries})
        unset(CONAN_FOUND_LIBRARY CACHE)
        find_library(CONAN_FOUND_LIBRARY NAME ${_LIBRARY_NAME} PATHS ${package_libdir} NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
        if(CONAN_FOUND_LIBRARY)
            message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${CONAN_FOUND_LIBRARY})
        else()
            message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
            set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
        endif()
    endforeach()
    unset(CONAN_FOUND_LIBRARY CACHE)
    set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
endfunction()

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
        if(CONAN_COMPILER STREQUAL "sun-cc")
            if(CONAN_LIBCXX STREQUAL "libCstd")
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -library=Cstd")
            elseif(CONAN_LIBCXX STREQUAL "libstdcxx")
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -library=stdcxx4")
            elseif(CONAN_LIBCXX STREQUAL "libstlport")
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -library=stlport4")
            elseif(CONAN_LIBCXX STREQUAL "libstdc++")
                set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -library=stdcpp")
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
    string(REPLACE "." ";" VERSION_LIST "${${VERSION_STRING}}")

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

    string(REGEX MATCH "compiler=([-A-Za-z0-9_ ]+)" _MATCHED ${CONANINFO})
    if(DEFINED CMAKE_MATCH_1)
        string(STRIP "${CMAKE_MATCH_1}" _CONAN_INFO_COMPILER)
        set(${CONAN_INFO_COMPILER} ${_CONAN_INFO_COMPILER} PARENT_SCOPE)
    endif()

    string(REGEX MATCH "compiler.version=([-A-Za-z0-9_.]+)" _MATCHED ${CONANINFO})
    if(DEFINED CMAKE_MATCH_1)
        string(STRIP "${CMAKE_MATCH_1}" _CONAN_INFO_COMPILER_VERSION)
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
    elseif(CONAN_COMPILER STREQUAL "gcc" OR CONAN_COMPILER MATCHES "clang" OR CONAN_COMPILER STREQUAL "sun-cc")
        if(NOT ${VERSION_MAJOR}.${VERSION_MINOR} VERSION_EQUAL CONAN_COMPILER_VERSION)
           conan_error_compiler_version()
        endif()
    else()
        message(STATUS "WARN: Unknown compiler '${CONAN_COMPILER}', skipping the version check...")
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

    if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL ${CMAKE_SYSTEM_NAME})
        set(CROSS_BUILDING 1)
    endif()

    # Avoid checks when cross compiling, apple-clang crashes because its APPLE but not apple-clang
    # Actually CMake is detecting "clang" when you are using apple-clang, only if CMP0025 is set to NEW will detect apple-clang
    if( (CONAN_COMPILER STREQUAL "Visual Studio" AND NOT CMAKE_CXX_COMPILER_ID MATCHES MSVC) OR
        (CONAN_COMPILER STREQUAL "gcc" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU") OR
        (CONAN_COMPILER STREQUAL "apple-clang" AND NOT CROSS_BUILDING AND (NOT APPLE OR NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")) OR
        (CONAN_COMPILER STREQUAL "clang" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang") OR
        (CONAN_COMPILER STREQUAL "sun-cc" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "SunPro") )
        message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}', is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}'")
    endif()


    if(NOT DEFINED CONAN_COMPILER_VERSION)
        message(STATUS "WARN: CONAN_COMPILER_VERSION variable not set, please make sure yourself "
                       "that your compiler version matches your declared settings")
        return()
    endif()
    check_compiler_version()
endfunction()

macro(conan_set_flags build_type)
    set(CMAKE_CXX_FLAGS${build_type} "${CMAKE_CXX_FLAGS${build_type}} ${CONAN_CXX_FLAGS${build_type}}")
    set(CMAKE_C_FLAGS${build_type} "${CMAKE_C_FLAGS${build_type}} ${CONAN_C_FLAGS${build_type}}")
    set(CMAKE_SHARED_LINKER_FLAGS${build_type} "${CMAKE_SHARED_LINKER_FLAGS${build_type}} ${CONAN_SHARED_LINKER_FLAGS${build_type}}")
    set(CMAKE_EXE_LINKER_FLAGS${build_type} "${CMAKE_EXE_LINKER_FLAGS${build_type}} ${CONAN_EXE_LINKER_FLAGS${build_type}}")
endmacro()

macro(conan_global_flags)
    if(CONAN_SYSTEM_INCLUDES)
        include_directories(SYSTEM ${CONAN_INCLUDE_DIRS}
                                   "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                   "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
    else()
        include_directories(${CONAN_INCLUDE_DIRS}
                            "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                            "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
    endif()

    link_directories(${CONAN_LIB_DIRS})

    conan_find_libraries_abs_path("${CONAN_LIBS_DEBUG}" "${CONAN_LIB_DIRS_DEBUG}"
                                  CONAN_LIBS_DEBUG)
    conan_find_libraries_abs_path("${CONAN_LIBS_RELEASE}" "${CONAN_LIB_DIRS_RELEASE}"
                                  CONAN_LIBS_RELEASE)

    add_compile_options(${CONAN_DEFINES}
                        "$<$<CONFIG:Debug>:${CONAN_DEFINES_DEBUG}>"
                        "$<$<CONFIG:Release>:${CONAN_DEFINES_RELEASE}>")

    conan_set_flags("")
    conan_set_flags("_RELEASE")
    conan_set_flags("_DEBUG")

endmacro()

macro(conan_target_link_libraries target)
    if(CONAN_TARGETS)
        target_link_libraries(${target} ${CONAN_TARGETS})
    else()
        target_link_libraries(${target} ${CONAN_LIBS})
        foreach(_LIB ${CONAN_LIBS_RELEASE})
            target_link_libraries(${target} optimized ${_LIB})
        endforeach()
        foreach(_LIB ${CONAN_LIBS_DEBUG})
            target_link_libraries(${target} debug ${_LIB})
        endforeach()
    endif()
endmacro()
"""

cmake_macros = """
macro(conan_basic_setup)
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
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
    # CMAKE_MODULE_PATH does not have Debug/Release config, but there are variables
    # CONAN_CMAKE_MODULE_PATH_DEBUG to be used by the consumer
    # CMake can find findXXX.cmake files in the root of packages
    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_MODULE_PATH})

    # Make find_package() to work
    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH} ${CMAKE_PREFIX_PATH})

    # Set the find root path (cross build)
    set(CMAKE_FIND_ROOT_PATH ${CONAN_CMAKE_FIND_ROOT_PATH} ${CMAKE_FIND_ROOT_PATH})
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM)
        set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_PROGRAM})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY)
        set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_LIBRARY})
    endif()
    if(CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE)
        set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ${CONAN_CMAKE_FIND_ROOT_PATH_MODE_INCLUDE})
    endif()
endmacro()

macro(conan_set_find_library_paths)
    # CMAKE_INCLUDE_PATH, CMAKE_LIBRARY_PATH does not have Debug/Release config, but there are variables
    # CONAN_INCLUDE_DIRS_DEBUG/RELEASE CONAN_LIB_DIRS_DEBUG/RELEASE to be used by the consumer
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

macro(conan_flags_setup)
    # Macro maintained for backwards compatibility
    conan_set_find_library_paths()
    conan_global_flags()
    conan_set_rpath()
    conan_set_vs_runtime()
    conan_set_libcxx()
endmacro()

""" + _cmake_common_macros


cmake_macros_multi = """
if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_release.cmake)
    include(${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_release.cmake)
else()
    message(FATAL_ERROR "No conanbuildinfo_release.cmake, please install the Release conf first")
endif()
if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_debug.cmake)
    include(${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_debug.cmake)
else()
    message(FATAL_ERROR "No conanbuildinfo_debug.cmake, please install the Debug conf first")
endif()

macro(conan_basic_setup)
    if(CONAN_EXPORTED)
        message(STATUS "Conan: called by CMake conan helper")
    endif()
    conan_check_compiler()
    # conan_output_dirs_setup()
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

macro(conan_set_vs_runtime)
    # This conan_set_vs_runtime is MORE opinionated than the regular one. It will
    # Leave the defaults MD (MDd) or replace them with MT (MTd) but taking into account the
    # debug, forcing MXd for debug builds. It will generate MSVCRT warnings if the dependencies
    # are installed with "conan install" and the wrong build time.
    if(CONAN_LINK_RUNTIME MATCHES "MT")
        if(DEFINED CMAKE_CXX_FLAGS_RELEASE)
            string(REPLACE "/MD" "/MT" CMAKE_CXX_FLAGS_RELEASE ${CMAKE_CXX_FLAGS_RELEASE})
        endif()
        if(DEFINED CMAKE_CXX_FLAGS_DEBUG)
            string(REPLACE "/MDd" "/MTd" CMAKE_CXX_FLAGS_DEBUG ${CMAKE_CXX_FLAGS_DEBUG})
        endif()
        if(DEFINED CMAKE_C_FLAGS_RELEASE)
            string(REPLACE "/MD" "/MT" CMAKE_C_FLAGS_RELEASE ${CMAKE_C_FLAGS_RELEASE})
        endif()
        if(DEFINED CMAKE_C_FLAGS_DEBUG)
            string(REPLACE "/MDd" "/MTd" CMAKE_C_FLAGS_DEBUG ${CMAKE_C_FLAGS_DEBUG})
        endif()
    endif()
endmacro()

macro(conan_set_find_paths)
    if(CMAKE_BUILD_TYPE)
        if(${CMAKE_BUILD_TYPE} MATCHES "Debug")
            set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_PREFIX_PATH})
            set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_MODULE_PATH})
        else()
            set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_PREFIX_PATH})
            set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_MODULE_PATH})
        endif()
    endif()
endmacro()
""" + _cmake_common_macros
