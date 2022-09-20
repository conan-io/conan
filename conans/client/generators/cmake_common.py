import textwrap

_cmake_single_dep_vars = """
#################
###  {dep}
#################
set(CONAN_{dep}_ROOT{build_type} {deps.rootpath})
set(CONAN_INCLUDE_DIRS_{dep}{build_type} {deps.include_paths})
set(CONAN_LIB_DIRS_{dep}{build_type} {deps.lib_paths})
set(CONAN_BIN_DIRS_{dep}{build_type} {deps.bin_paths})
set(CONAN_RES_DIRS_{dep}{build_type} {deps.res_paths})
set(CONAN_SRC_DIRS_{dep}{build_type} {deps.src_paths})
set(CONAN_BUILD_DIRS_{dep}{build_type} {deps.build_paths})
set(CONAN_FRAMEWORK_DIRS_{dep}{build_type} {deps.framework_paths})
set(CONAN_LIBS_{dep}{build_type} {deps.libs})
set(CONAN_PKG_LIBS_{dep}{build_type} {deps.libs})
set(CONAN_SYSTEM_LIBS_{dep}{build_type} {deps.system_libs})
set(CONAN_FRAMEWORKS_{dep}{build_type} {deps.frameworks})
set(CONAN_FRAMEWORKS_FOUND_{dep}{build_type} "")  # Will be filled later
set(CONAN_DEFINES_{dep}{build_type} {deps.defines})
set(CONAN_BUILD_MODULES_PATHS_{dep}{build_type} {deps.build_modules_paths})
# COMPILE_DEFINITIONS are equal to CONAN_DEFINES without -D, for targets
set(CONAN_COMPILE_DEFINITIONS_{dep}{build_type} {deps.compile_definitions})

set(CONAN_C_FLAGS_{dep}{build_type} "{deps.cflags}")
set(CONAN_CXX_FLAGS_{dep}{build_type} "{deps.cxxflags}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type} "{deps.sharedlinkflags}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type} "{deps.exelinkflags}")

# For modern cmake targets we use the list variables (separated with ;)
set(CONAN_C_FLAGS_{dep}{build_type}_LIST "{deps.cflags_list}")
set(CONAN_CXX_FLAGS_{dep}{build_type}_LIST "{deps.cxxflags_list}")
set(CONAN_SHARED_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.sharedlinkflags_list}")
set(CONAN_EXE_LINKER_FLAGS_{dep}{build_type}_LIST "{deps.exelinkflags_list}")

# Apple Frameworks
conan_find_apple_frameworks(CONAN_FRAMEWORKS_FOUND_{dep}{build_type} "${{CONAN_FRAMEWORKS_{dep}{build_type}}}" "_{dep}" "{build_type}")
# Append to aggregated values variable
set(CONAN_LIBS_{dep}{build_type} ${{CONAN_PKG_LIBS_{dep}{build_type}}} ${{CONAN_SYSTEM_LIBS_{dep}{build_type}}} ${{CONAN_FRAMEWORKS_FOUND_{dep}{build_type}}})
"""


def _cmake_string_representation(value):
    """Escapes the specified string for use in a CMake command surrounded with double quotes
       :param value the string to escape"""
    return '"{0}"'.format(value.replace('\\', '\\\\')
                               .replace('$', '\\$')
                               .replace('"', '\\"'))


def _build_type_str(build_type):
    if build_type:
        return "_" + str(build_type).upper()
    return ""


def cmake_user_info_vars(deps_user_info):
    lines = []
    for dep, the_vars in deps_user_info.items():
        for name, value in the_vars.vars.items():
            lines.append('set(CONAN_USER_%s_%s %s)'
                         % (dep.upper(), name, _cmake_string_representation(value)))
    return "\n".join(lines)


def cmake_dependency_vars(name, deps, build_type=""):
    build_type = _build_type_str(build_type)
    return _cmake_single_dep_vars.format(dep=name.upper(), deps=deps, build_type=build_type)


_cmake_package_info = """set(CONAN_PACKAGE_NAME {name})
set(CONAN_PACKAGE_VERSION {version})
"""


def cmake_package_info(name, version):
    return _cmake_package_info.format(name=name, version=version)


def cmake_settings_info(settings):
    settings_info = ""
    for item in settings.items():
        key, value = item
        name = "CONAN_SETTINGS_%s" % key.upper().replace(".", "_")
        settings_info += "set({key} {value})\n".format(key=name,
                                                       value=_cmake_string_representation(value))
    return settings_info


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
set(CONAN_FRAMEWORK_DIRS{build_type} {deps.framework_paths} ${{CONAN_FRAMEWORK_DIRS{build_type}}})
set(CONAN_LIBS{build_type} {deps.libs} ${{CONAN_LIBS{build_type}}})
set(CONAN_PKG_LIBS{build_type} {deps.libs} ${{CONAN_PKG_LIBS{build_type}}})
set(CONAN_SYSTEM_LIBS{build_type} {deps.system_libs} ${{CONAN_SYSTEM_LIBS{build_type}}})
set(CONAN_FRAMEWORKS{build_type} {deps.frameworks} ${{CONAN_FRAMEWORKS{build_type}}})
set(CONAN_FRAMEWORKS_FOUND{build_type} "")  # Will be filled later
set(CONAN_DEFINES{build_type} {deps.defines} ${{CONAN_DEFINES{build_type}}})
set(CONAN_BUILD_MODULES_PATHS{build_type} {deps.build_modules_paths} ${{CONAN_BUILD_MODULES_PATHS{build_type}}})
set(CONAN_CMAKE_MODULE_PATH{build_type} {deps.build_paths} ${{CONAN_CMAKE_MODULE_PATH{build_type}}})

set(CONAN_CXX_FLAGS{build_type} "{deps.cxxflags} ${{CONAN_CXX_FLAGS{build_type}}}")
set(CONAN_SHARED_LINKER_FLAGS{build_type} "{deps.sharedlinkflags} ${{CONAN_SHARED_LINKER_FLAGS{build_type}}}")
set(CONAN_EXE_LINKER_FLAGS{build_type} "{deps.exelinkflags} ${{CONAN_EXE_LINKER_FLAGS{build_type}}}")
set(CONAN_C_FLAGS{build_type} "{deps.cflags} ${{CONAN_C_FLAGS{build_type}}}")

# Apple Frameworks
conan_find_apple_frameworks(CONAN_FRAMEWORKS_FOUND{build_type} "${{CONAN_FRAMEWORKS{build_type}}}" "" "{build_type}")
# Append to aggregated values variable: Use CONAN_LIBS instead of CONAN_PKG_LIBS to include user appended vars
set(CONAN_LIBS{build_type} ${{CONAN_LIBS{build_type}}} ${{CONAN_SYSTEM_LIBS{build_type}}} ${{CONAN_FRAMEWORKS_FOUND{build_type}}})
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
    set(_CONAN_PKG_LIBS_{uname}_DEPENDENCIES "${{CONAN_SYSTEM_LIBS_{uname}}} ${{CONAN_FRAMEWORKS_FOUND_{uname}}} {deps}")
    string(REPLACE " " ";" _CONAN_PKG_LIBS_{uname}_DEPENDENCIES "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES}}")
    conan_package_library_targets("${{CONAN_PKG_LIBS_{uname}}}" "${{CONAN_LIB_DIRS_{uname}}}"
                                  CONAN_PACKAGE_TARGETS_{uname} "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES}}"
                                  "" {pkg_name})
    set(_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_DEBUG "${{CONAN_SYSTEM_LIBS_{uname}_DEBUG}} ${{CONAN_FRAMEWORKS_FOUND_{uname}_DEBUG}} {deps}")
    string(REPLACE " " ";" _CONAN_PKG_LIBS_{uname}_DEPENDENCIES_DEBUG "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_DEBUG}}")
    conan_package_library_targets("${{CONAN_PKG_LIBS_{uname}_DEBUG}}" "${{CONAN_LIB_DIRS_{uname}_DEBUG}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_DEBUG "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_DEBUG}}"
                                  "debug" {pkg_name})
    set(_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELEASE "${{CONAN_SYSTEM_LIBS_{uname}_RELEASE}} ${{CONAN_FRAMEWORKS_FOUND_{uname}_RELEASE}} {deps}")
    string(REPLACE " " ";" _CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELEASE "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELEASE}}")
    conan_package_library_targets("${{CONAN_PKG_LIBS_{uname}_RELEASE}}" "${{CONAN_LIB_DIRS_{uname}_RELEASE}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_RELEASE "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELEASE}}"
                                  "release" {pkg_name})
    set(_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELWITHDEBINFO "${{CONAN_SYSTEM_LIBS_{uname}_RELWITHDEBINFO}} ${{CONAN_FRAMEWORKS_FOUND_{uname}_RELWITHDEBINFO}} {deps}")
    string(REPLACE " " ";" _CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELWITHDEBINFO "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELWITHDEBINFO}}")
    conan_package_library_targets("${{CONAN_PKG_LIBS_{uname}_RELWITHDEBINFO}}" "${{CONAN_LIB_DIRS_{uname}_RELWITHDEBINFO}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_RELWITHDEBINFO "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELWITHDEBINFO}}"
                                  "relwithdebinfo" {pkg_name})
    set(_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_MINSIZEREL "${{CONAN_SYSTEM_LIBS_{uname}_MINSIZEREL}} ${{CONAN_FRAMEWORKS_FOUND_{uname}_MINSIZEREL}} {deps}")
    string(REPLACE " " ";" _CONAN_PKG_LIBS_{uname}_DEPENDENCIES_MINSIZEREL "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_MINSIZEREL}}")
    conan_package_library_targets("${{CONAN_PKG_LIBS_{uname}_MINSIZEREL}}" "${{CONAN_LIB_DIRS_{uname}_MINSIZEREL}}"
                                  CONAN_PACKAGE_TARGETS_{uname}_MINSIZEREL "${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_MINSIZEREL}}"
                                  "minsizerel" {pkg_name})

    add_library({name} INTERFACE IMPORTED)

    # Property INTERFACE_LINK_FLAGS do not work, necessary to add to INTERFACE_LINK_LIBRARIES
    set_property(TARGET {name} PROPERTY INTERFACE_LINK_LIBRARIES ${{CONAN_PACKAGE_TARGETS_{uname}}} ${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES}}
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{CONAN_EXE_LINKER_FLAGS_{uname}_LIST}}>

                                                                 $<$<CONFIG:Release>:${{CONAN_PACKAGE_TARGETS_{uname}_RELEASE}} ${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELEASE}}
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELEASE_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{CONAN_EXE_LINKER_FLAGS_{uname}_RELEASE_LIST}}>>

                                                                 $<$<CONFIG:RelWithDebInfo>:${{CONAN_PACKAGE_TARGETS_{uname}_RELWITHDEBINFO}} ${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_RELWITHDEBINFO}}
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELWITHDEBINFO_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_RELWITHDEBINFO_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{CONAN_EXE_LINKER_FLAGS_{uname}_RELWITHDEBINFO_LIST}}>>

                                                                 $<$<CONFIG:MinSizeRel>:${{CONAN_PACKAGE_TARGETS_{uname}_MINSIZEREL}} ${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_MINSIZEREL}}
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_MINSIZEREL_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_MINSIZEREL_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{CONAN_EXE_LINKER_FLAGS_{uname}_MINSIZEREL_LIST}}>>

                                                                 $<$<CONFIG:Debug>:${{CONAN_PACKAGE_TARGETS_{uname}_DEBUG}} ${{_CONAN_PKG_LIBS_{uname}_DEPENDENCIES_DEBUG}}
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:${{CONAN_SHARED_LINKER_FLAGS_{uname}_DEBUG_LIST}}>
                                                                 $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:${{CONAN_EXE_LINKER_FLAGS_{uname}_DEBUG_LIST}}>>)
    set_property(TARGET {name} PROPERTY INTERFACE_INCLUDE_DIRECTORIES ${{CONAN_INCLUDE_DIRS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_INCLUDE_DIRS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_INCLUDE_DIRS_{uname}_RELWITHDEBINFO}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_INCLUDE_DIRS_{uname}_MINSIZEREL}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_INCLUDE_DIRS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{CONAN_COMPILE_DEFINITIONS_{uname}}}
                                                                      $<$<CONFIG:Release>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELEASE}}>
                                                                      $<$<CONFIG:RelWithDebInfo>:${{CONAN_COMPILE_DEFINITIONS_{uname}_RELWITHDEBINFO}}>
                                                                      $<$<CONFIG:MinSizeRel>:${{CONAN_COMPILE_DEFINITIONS_{uname}_MINSIZEREL}}>
                                                                      $<$<CONFIG:Debug>:${{CONAN_COMPILE_DEFINITIONS_{uname}_DEBUG}}>)
    set_property(TARGET {name} PROPERTY INTERFACE_COMPILE_OPTIONS ${{CONAN_C_FLAGS_{uname}_LIST}} ${{CONAN_CXX_FLAGS_{uname}_LIST}}
                                                                  $<$<CONFIG:Release>:${{CONAN_C_FLAGS_{uname}_RELEASE_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELEASE_LIST}}>
                                                                  $<$<CONFIG:RelWithDebInfo>:${{CONAN_C_FLAGS_{uname}_RELWITHDEBINFO_LIST}} ${{CONAN_CXX_FLAGS_{uname}_RELWITHDEBINFO_LIST}}>
                                                                  $<$<CONFIG:MinSizeRel>:${{CONAN_C_FLAGS_{uname}_MINSIZEREL_LIST}} ${{CONAN_CXX_FLAGS_{uname}_MINSIZEREL_LIST}}>
                                                                  $<$<CONFIG:Debug>:${{CONAN_C_FLAGS_{uname}_DEBUG_LIST}}  ${{CONAN_CXX_FLAGS_{uname}_DEBUG_LIST}}>)
"""


def generate_targets_section(dependencies, generator_name):
    section = []
    section.append("\n###  Definition of macros and functions ###\n")
    section.append('macro(conan_define_targets)\n'
                   '    if(${CMAKE_VERSION} VERSION_LESS "3.1.2")\n'
                   '        message(FATAL_ERROR "TARGETS not supported by your CMake version!")\n'
                   '    endif()  # CMAKE > 3.x\n'
                   '    set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} ${CONAN_CMD_CXX_FLAGS}")\n'
                   '    set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} ${CONAN_CMD_C_FLAGS}")\n'
                   '    set(CMAKE_SHARED_LINKER_FLAGS "${CMAKE_SHARED_LINKER_FLAGS} ${CONAN_CMD_SHARED_LINKER_FLAGS}")\n')
    dependencies_dict = {name: dep_info for name, dep_info in dependencies}
    for _, dep_info in dependencies:
        dep_name = dep_info.get_name(generator_name)
        use_deps = ["CONAN_PKG::%s" % dependencies_dict[d].get_name(generator_name) for d in dep_info.public_deps]
        deps = "" if not use_deps else " ".join(use_deps)
        section.append(_target_template.format(name="CONAN_PKG::%s" % dep_name, deps=deps,
                                               uname=dep_name.upper(), pkg_name=dep_name))

    all_targets = " ".join(["CONAN_PKG::%s" % dep_info.get_name(generator_name) for _, dep_info in dependencies])
    section.append('    set(CONAN_TARGETS %s)\n' % all_targets)
    section.append('endmacro()\n')
    return section


class CMakeCommonMacros:
    # Group definition of CMake macros and functions used for many different generators
    conan_message = textwrap.dedent("""
        function(conan_message MESSAGE_OUTPUT)
            if(NOT CONAN_CMAKE_SILENT_OUTPUT)
                message(${ARGV${0}})
            endif()
        endfunction()
    """)

    # this function gets the policy without raising an error for earlier versions than the policy
    conan_get_policy = textwrap.dedent("""
        function(conan_get_policy policy_id policy)
            if(POLICY "${policy_id}")
                cmake_policy(GET "${policy_id}" _policy)
                set(${policy} "${_policy}" PARENT_SCOPE)
            else()
                set(${policy} "" PARENT_SCOPE)
            endif()
        endfunction()
    """)

    conan_find_libraries_abs_path = textwrap.dedent("""
        function(conan_find_libraries_abs_path libraries package_libdir libraries_abs_path)
            foreach(_LIBRARY_NAME ${libraries})
                find_library(CONAN_FOUND_LIBRARY NAMES ${_LIBRARY_NAME} PATHS ${package_libdir}
                             NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
                if(CONAN_FOUND_LIBRARY)
                    conan_message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${CONAN_FOUND_LIBRARY})
                else()
                    conan_message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
                endif()
                unset(CONAN_FOUND_LIBRARY CACHE)
            endforeach()
            set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
        endfunction()
    """)

    conan_package_library_targets = textwrap.dedent("""
        function(conan_package_library_targets libraries package_libdir libraries_abs_path deps build_type package_name)
            unset(_CONAN_ACTUAL_TARGETS CACHE)
            unset(_CONAN_FOUND_SYSTEM_LIBS CACHE)
            foreach(_LIBRARY_NAME ${libraries})
                find_library(CONAN_FOUND_LIBRARY NAMES ${_LIBRARY_NAME} PATHS ${package_libdir}
                             NO_DEFAULT_PATH NO_CMAKE_FIND_ROOT_PATH)
                if(CONAN_FOUND_LIBRARY)
                    conan_message(STATUS "Library ${_LIBRARY_NAME} found ${CONAN_FOUND_LIBRARY}")
                    set(_LIB_NAME CONAN_LIB::${package_name}_${_LIBRARY_NAME}${build_type})
                    add_library(${_LIB_NAME} UNKNOWN IMPORTED)
                    set_target_properties(${_LIB_NAME} PROPERTIES IMPORTED_LOCATION ${CONAN_FOUND_LIBRARY})
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIB_NAME})
                    set(_CONAN_ACTUAL_TARGETS ${_CONAN_ACTUAL_TARGETS} ${_LIB_NAME})
                else()
                    conan_message(STATUS "Library ${_LIBRARY_NAME} not found in package, might be system one")
                    set(CONAN_FULLPATH_LIBS ${CONAN_FULLPATH_LIBS} ${_LIBRARY_NAME})
                    set(_CONAN_FOUND_SYSTEM_LIBS "${_CONAN_FOUND_SYSTEM_LIBS};${_LIBRARY_NAME}")
                endif()
                unset(CONAN_FOUND_LIBRARY CACHE)
            endforeach()

            # Add all dependencies to all targets
            string(REPLACE " " ";" deps_list "${deps}")
            foreach(_CONAN_ACTUAL_TARGET ${_CONAN_ACTUAL_TARGETS})
                set_property(TARGET ${_CONAN_ACTUAL_TARGET} PROPERTY INTERFACE_LINK_LIBRARIES "${_CONAN_FOUND_SYSTEM_LIBS};${deps_list}")
            endforeach()

            set(${libraries_abs_path} ${CONAN_FULLPATH_LIBS} PARENT_SCOPE)
        endfunction()
    """)

    conan_set_libcxx = textwrap.dedent("""
        macro(conan_set_libcxx)
            if(DEFINED CONAN_LIBCXX)
                conan_message(STATUS "Conan: C++ stdlib: ${CONAN_LIBCXX}")
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
    """)

    conan_set_std = textwrap.dedent("""
        macro(conan_set_std)
            conan_message(STATUS "Conan: Adjusting language standard")
            # Do not warn "Manually-specified variables were not used by the project"
            set(ignorevar "${CONAN_STD_CXX_FLAG}${CONAN_CMAKE_CXX_STANDARD}${CONAN_CMAKE_CXX_EXTENSIONS}")
            if (CMAKE_VERSION VERSION_LESS "3.1" OR
                (CMAKE_VERSION VERSION_LESS "3.12" AND ("${CONAN_CMAKE_CXX_STANDARD}" STREQUAL "20" OR "${CONAN_CMAKE_CXX_STANDARD}" STREQUAL "gnu20")))
                if(CONAN_STD_CXX_FLAG)
                    conan_message(STATUS "Conan setting CXX_FLAGS flags: ${CONAN_STD_CXX_FLAG}")
                    set(CMAKE_CXX_FLAGS "${CONAN_STD_CXX_FLAG} ${CMAKE_CXX_FLAGS}")
                endif()
            else()
                if(CONAN_CMAKE_CXX_STANDARD)
                    conan_message(STATUS "Conan setting CPP STANDARD: ${CONAN_CMAKE_CXX_STANDARD} WITH EXTENSIONS ${CONAN_CMAKE_CXX_EXTENSIONS}")
                    set(CMAKE_CXX_STANDARD ${CONAN_CMAKE_CXX_STANDARD})
                    set(CMAKE_CXX_EXTENSIONS ${CONAN_CMAKE_CXX_EXTENSIONS})
                endif()
            endif()
        endmacro()
    """)

    conan_set_rpath = textwrap.dedent("""
        macro(conan_set_rpath)
            conan_message(STATUS "Conan: Adjusting default RPATHs Conan policies")
            if(APPLE)
                # https://cmake.org/Wiki/CMake_RPATH_handling
                # CONAN GUIDE: All generated libraries should have the id and dependencies to other
                # dylibs without path, just the name, EX:
                # libMyLib1.dylib:
                #     libMyLib1.dylib (compatibility version 0.0.0, current version 0.0.0)
                #     libMyLib0.dylib (compatibility version 0.0.0, current version 0.0.0)
                #     /usr/lib/libc++.1.dylib (compatibility version 1.0.0, current version 120.0.0)
                #     /usr/lib/libSystem.B.dylib (compatibility version 1.0.0, current version 1197.1.1)
                # AVOID RPATH FOR *.dylib, ALL LIBS BETWEEN THEM AND THE EXE
                # SHOULD BE ON THE LINKER RESOLVER PATH (./ IS ONE OF THEM)
                set(CMAKE_SKIP_RPATH 1 CACHE BOOL "rpaths" FORCE)
                # Policy CMP0068
                # We want the old behavior, in CMake >= 3.9 CMAKE_SKIP_RPATH won't affect the install_name in OSX
                set(CMAKE_INSTALL_NAME_DIR "")
            endif()
        endmacro()
    """)

    conan_set_fpic = textwrap.dedent("""
        macro(conan_set_fpic)
            if(DEFINED CONAN_CMAKE_POSITION_INDEPENDENT_CODE)
                conan_message(STATUS "Conan: Adjusting fPIC flag (${CONAN_CMAKE_POSITION_INDEPENDENT_CODE})")
                set(CMAKE_POSITION_INDEPENDENT_CODE ${CONAN_CMAKE_POSITION_INDEPENDENT_CODE})
            endif()
        endmacro()
    """)

    conan_output_dirs_setup = textwrap.dedent("""
        macro(conan_output_dirs_setup)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/bin)
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELEASE ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})
            set(CMAKE_RUNTIME_OUTPUT_DIRECTORY_DEBUG ${CMAKE_RUNTIME_OUTPUT_DIRECTORY})

            set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
            set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELEASE ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
            set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
            set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})
            set(CMAKE_ARCHIVE_OUTPUT_DIRECTORY_DEBUG ${CMAKE_ARCHIVE_OUTPUT_DIRECTORY})

            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_BINARY_DIR}/lib)
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELEASE ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_RELWITHDEBINFO ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_MINSIZEREL ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})
            set(CMAKE_LIBRARY_OUTPUT_DIRECTORY_DEBUG ${CMAKE_LIBRARY_OUTPUT_DIRECTORY})
        endmacro()
    """)

    conan_split_version = textwrap.dedent("""
        macro(conan_split_version VERSION_STRING MAJOR MINOR)
            #make a list from the version string
            string(REPLACE "." ";" VERSION_LIST "${VERSION_STRING}")

            #write output values
            list(LENGTH VERSION_LIST _version_len)
            list(GET VERSION_LIST 0 ${MAJOR})
            if(${_version_len} GREATER 1)
                list(GET VERSION_LIST 1 ${MINOR})
            endif()
        endmacro()
    """)

    conan_error_compiler_version = textwrap.dedent("""
        macro(conan_error_compiler_version)
            message(FATAL_ERROR "Detected a mismatch for the compiler version between your conan profile settings and CMake: \\n"
                                "Compiler version specified in your conan profile: ${CONAN_COMPILER_VERSION}\\n"
                                "Compiler version detected in CMake: ${VERSION_MAJOR}.${VERSION_MINOR}\\n"
                                "Please check your conan profile settings (conan profile show [default|your_profile_name])\\n"
                                "P.S. You may set CONAN_DISABLE_CHECK_COMPILER CMake variable in order to disable this check."
                   )
        endmacro()
    """)

    conan_get_compiler = textwrap.dedent("""
        function(conan_get_compiler CONAN_INFO_COMPILER CONAN_INFO_COMPILER_VERSION)
            conan_message(STATUS "Current conanbuildinfo.cmake directory: " ${_CONAN_CURRENT_DIR})
            if(NOT EXISTS ${_CONAN_CURRENT_DIR}/conaninfo.txt)
                conan_message(STATUS "WARN: conaninfo.txt not found")
                return()
            endif()

            file (READ "${_CONAN_CURRENT_DIR}/conaninfo.txt" CONANINFO)

            # MATCHALL will match all, including the last one, which is the full_settings one
            string(REGEX MATCH "full_settings.*" _FULL_SETTINGS_MATCHED ${CONANINFO})
            string(REGEX MATCH "compiler=([-A-Za-z0-9_ ]+)" _MATCHED ${_FULL_SETTINGS_MATCHED})
            if(DEFINED CMAKE_MATCH_1)
                string(STRIP "${CMAKE_MATCH_1}" _CONAN_INFO_COMPILER)
                set(${CONAN_INFO_COMPILER} ${_CONAN_INFO_COMPILER} PARENT_SCOPE)
            endif()

            string(REGEX MATCH "compiler.version=([-A-Za-z0-9_.]+)" _MATCHED ${_FULL_SETTINGS_MATCHED})
            if(DEFINED CMAKE_MATCH_1)
                string(STRIP "${CMAKE_MATCH_1}" _CONAN_INFO_COMPILER_VERSION)
                set(${CONAN_INFO_COMPILER_VERSION} ${_CONAN_INFO_COMPILER_VERSION} PARENT_SCOPE)
            endif()
        endfunction()
    """)
    check_compiler_version = textwrap.dedent("""
        function(check_compiler_version)
            conan_split_version(${CMAKE_CXX_COMPILER_VERSION} VERSION_MAJOR VERSION_MINOR)
            if(DEFINED CONAN_SETTINGS_COMPILER_TOOLSET)
               conan_message(STATUS "Conan: Skipping compiler check: Declared 'compiler.toolset'")
               return()
            endif()
            if(CMAKE_CXX_COMPILER_ID MATCHES MSVC)
                # MSVC_VERSION is defined since 2.8.2 at least
                # https://cmake.org/cmake/help/v2.8.2/cmake.html#variable:MSVC_VERSION
                # https://cmake.org/cmake/help/v3.14/variable/MSVC_VERSION.html
                if(
                    # 1930 = VS 17.0 (v143 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "17" AND NOT((MSVC_VERSION EQUAL 1930) OR (MSVC_VERSION GREATER 1930))) OR
                    # 1920-1929 = VS 16.0 (v142 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "16" AND NOT((MSVC_VERSION GREATER 1919) AND (MSVC_VERSION LESS 1930))) OR
                    # 1910-1919 = VS 15.0 (v141 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "15" AND NOT((MSVC_VERSION GREATER 1909) AND (MSVC_VERSION LESS 1920))) OR
                    # 1900      = VS 14.0 (v140 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "14" AND NOT(MSVC_VERSION EQUAL 1900)) OR
                    # 1800      = VS 12.0 (v120 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "12" AND NOT VERSION_MAJOR STREQUAL "18") OR
                    # 1700      = VS 11.0 (v110 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "11" AND NOT VERSION_MAJOR STREQUAL "17") OR
                    # 1600      = VS 10.0 (v100 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "10" AND NOT VERSION_MAJOR STREQUAL "16") OR
                    # 1500      = VS  9.0 (v90 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "9" AND NOT VERSION_MAJOR STREQUAL "15") OR
                    # 1400      = VS  8.0 (v80 toolset)
                    (CONAN_COMPILER_VERSION STREQUAL "8" AND NOT VERSION_MAJOR STREQUAL "14") OR
                    # 1310      = VS  7.1, 1300      = VS  7.0
                    (CONAN_COMPILER_VERSION STREQUAL "7" AND NOT VERSION_MAJOR STREQUAL "13") OR
                    # 1200      = VS  6.0
                    (CONAN_COMPILER_VERSION STREQUAL "6" AND NOT VERSION_MAJOR STREQUAL "12") )
                    conan_error_compiler_version()
                endif()
            elseif(CONAN_COMPILER STREQUAL "gcc")
                conan_split_version(${CONAN_COMPILER_VERSION} CONAN_COMPILER_MAJOR CONAN_COMPILER_MINOR)
                set(_CHECK_VERSION ${VERSION_MAJOR}.${VERSION_MINOR})
                set(_CONAN_VERSION ${CONAN_COMPILER_MAJOR}.${CONAN_COMPILER_MINOR})
                if(NOT ${CONAN_COMPILER_VERSION} VERSION_LESS 5.0)
                    conan_message(STATUS "Conan: Compiler GCC>=5, checking major version ${CONAN_COMPILER_VERSION}")
                    conan_split_version(${CONAN_COMPILER_VERSION} CONAN_COMPILER_MAJOR CONAN_COMPILER_MINOR)
                    if("${CONAN_COMPILER_MINOR}" STREQUAL "")
                        set(_CHECK_VERSION ${VERSION_MAJOR})
                        set(_CONAN_VERSION ${CONAN_COMPILER_MAJOR})
                    endif()
                endif()
                conan_message(STATUS "Conan: Checking correct version: ${_CHECK_VERSION}")
                if(NOT ${_CHECK_VERSION} VERSION_EQUAL ${_CONAN_VERSION})
                    conan_error_compiler_version()
                endif()
            elseif(CONAN_COMPILER STREQUAL "clang")
                conan_split_version(${CONAN_COMPILER_VERSION} CONAN_COMPILER_MAJOR CONAN_COMPILER_MINOR)
                set(_CHECK_VERSION ${VERSION_MAJOR}.${VERSION_MINOR})
                set(_CONAN_VERSION ${CONAN_COMPILER_MAJOR}.${CONAN_COMPILER_MINOR})
                if(NOT ${CONAN_COMPILER_VERSION} VERSION_LESS 8.0)
                    conan_message(STATUS "Conan: Compiler Clang>=8, checking major version ${CONAN_COMPILER_VERSION}")
                    if("${CONAN_COMPILER_MINOR}" STREQUAL "")
                        set(_CHECK_VERSION ${VERSION_MAJOR})
                        set(_CONAN_VERSION ${CONAN_COMPILER_MAJOR})
                    endif()
                endif()
                conan_message(STATUS "Conan: Checking correct version: ${_CHECK_VERSION}")
                if(NOT ${_CHECK_VERSION} VERSION_EQUAL ${_CONAN_VERSION})
                    conan_error_compiler_version()
                endif()
            elseif(CONAN_COMPILER STREQUAL "apple-clang" OR CONAN_COMPILER STREQUAL "sun-cc" OR CONAN_COMPILER STREQUAL "mcst-lcc")
                conan_split_version(${CONAN_COMPILER_VERSION} CONAN_COMPILER_MAJOR CONAN_COMPILER_MINOR)
                if(${CONAN_COMPILER_MAJOR} VERSION_GREATER_EQUAL "13" AND "${CONAN_COMPILER_MINOR}" STREQUAL "" AND ${CONAN_COMPILER_MAJOR} VERSION_EQUAL ${VERSION_MAJOR})
                   # This is correct,  13.X is considered 13
                elseif(NOT ${VERSION_MAJOR}.${VERSION_MINOR} VERSION_EQUAL ${CONAN_COMPILER_MAJOR}.${CONAN_COMPILER_MINOR})
                   conan_error_compiler_version()
                endif()
            elseif(CONAN_COMPILER STREQUAL "intel")
                conan_split_version(${CONAN_COMPILER_VERSION} CONAN_COMPILER_MAJOR CONAN_COMPILER_MINOR)
                if(NOT ${CONAN_COMPILER_VERSION} VERSION_LESS 19.1)
                    if(NOT ${VERSION_MAJOR}.${VERSION_MINOR} VERSION_EQUAL ${CONAN_COMPILER_MAJOR}.${CONAN_COMPILER_MINOR})
                       conan_error_compiler_version()
                    endif()
                else()
                    if(NOT ${VERSION_MAJOR} VERSION_EQUAL ${CONAN_COMPILER_MAJOR})
                       conan_error_compiler_version()
                    endif()
                endif()
            else()
                conan_message(STATUS "WARN: Unknown compiler '${CONAN_COMPILER}', skipping the version check...")
            endif()
        endfunction()
    """)

    conan_check_compiler = textwrap.dedent("""
        function(conan_check_compiler)
            if(CONAN_DISABLE_CHECK_COMPILER)
                conan_message(STATUS "WARN: Disabled conan compiler checks")
                return()
            endif()
            if(NOT DEFINED CMAKE_CXX_COMPILER_ID)
                if(DEFINED CMAKE_C_COMPILER_ID)
                    conan_message(STATUS "This project seems to be plain C, using '${CMAKE_C_COMPILER_ID}' compiler")
                    set(CMAKE_CXX_COMPILER_ID ${CMAKE_C_COMPILER_ID})
                    set(CMAKE_CXX_COMPILER_VERSION ${CMAKE_C_COMPILER_VERSION})
                else()
                    message(FATAL_ERROR "This project seems to be plain C, but no compiler defined")
                endif()
            endif()
            if(NOT CMAKE_CXX_COMPILER_ID AND NOT CMAKE_C_COMPILER_ID)
                # This use case happens when compiler is not identified by CMake, but the compilers are there and work
                conan_message(STATUS "*** WARN: CMake was not able to identify a C or C++ compiler ***")
                conan_message(STATUS "*** WARN: Disabling compiler checks. Please make sure your settings match your environment ***")
                return()
            endif()
            if(NOT DEFINED CONAN_COMPILER)
                conan_get_compiler(CONAN_COMPILER CONAN_COMPILER_VERSION)
                if(NOT DEFINED CONAN_COMPILER)
                    conan_message(STATUS "WARN: CONAN_COMPILER variable not set, please make sure yourself that "
                                  "your compiler and version matches your declared settings")
                    return()
                endif()
            endif()

            if(NOT CMAKE_HOST_SYSTEM_NAME STREQUAL ${CMAKE_SYSTEM_NAME})
                set(CROSS_BUILDING 1)
            endif()

            # If using VS, verify toolset
            if (CONAN_COMPILER STREQUAL "Visual Studio")
                if (CONAN_SETTINGS_COMPILER_TOOLSET MATCHES "LLVM" OR
                    CONAN_SETTINGS_COMPILER_TOOLSET MATCHES "llvm" OR
                    CONAN_SETTINGS_COMPILER_TOOLSET MATCHES "clang" OR
                    CONAN_SETTINGS_COMPILER_TOOLSET MATCHES "Clang")
                    set(EXPECTED_CMAKE_CXX_COMPILER_ID "Clang")
                elseif (CONAN_SETTINGS_COMPILER_TOOLSET MATCHES "Intel")
                    set(EXPECTED_CMAKE_CXX_COMPILER_ID "Intel")
                else()
                    set(EXPECTED_CMAKE_CXX_COMPILER_ID "MSVC")
                endif()

                if (NOT CMAKE_CXX_COMPILER_ID MATCHES ${EXPECTED_CMAKE_CXX_COMPILER_ID})
                    message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}'. Toolset specifies compiler as '${EXPECTED_CMAKE_CXX_COMPILER_ID}' "
                                        "but CMake detected '${CMAKE_CXX_COMPILER_ID}'")
                endif()

            # Avoid checks when cross compiling, apple-clang crashes because its APPLE but not apple-clang
            # Actually CMake is detecting "clang" when you are using apple-clang, only if CMP0025 is set to NEW will detect apple-clang
            elseif((CONAN_COMPILER STREQUAL "gcc" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "GNU") OR
                (CONAN_COMPILER STREQUAL "apple-clang" AND NOT CROSS_BUILDING AND (NOT APPLE OR NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang")) OR
                (CONAN_COMPILER STREQUAL "clang" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "Clang") OR
                (CONAN_COMPILER STREQUAL "sun-cc" AND NOT CMAKE_CXX_COMPILER_ID MATCHES "SunPro") )
                message(FATAL_ERROR "Incorrect '${CONAN_COMPILER}', is not the one detected by CMake: '${CMAKE_CXX_COMPILER_ID}'")
            endif()


            if(NOT DEFINED CONAN_COMPILER_VERSION)
                conan_message(STATUS "WARN: CONAN_COMPILER_VERSION variable not set, please make sure yourself "
                                     "that your compiler version matches your declared settings")
                return()
            endif()
            check_compiler_version()
        endfunction()
    """)

    conan_set_flags = textwrap.dedent("""
        macro(conan_set_flags build_type)
            set(CMAKE_CXX_FLAGS${build_type} "${CMAKE_CXX_FLAGS${build_type}} ${CONAN_CXX_FLAGS${build_type}}")
            set(CMAKE_C_FLAGS${build_type} "${CMAKE_C_FLAGS${build_type}} ${CONAN_C_FLAGS${build_type}}")
            set(CMAKE_SHARED_LINKER_FLAGS${build_type} "${CMAKE_SHARED_LINKER_FLAGS${build_type}} ${CONAN_SHARED_LINKER_FLAGS${build_type}}")
            set(CMAKE_EXE_LINKER_FLAGS${build_type} "${CMAKE_EXE_LINKER_FLAGS${build_type}} ${CONAN_EXE_LINKER_FLAGS${build_type}}")
        endmacro()
    """)

    conan_global_flags = textwrap.dedent("""
        macro(conan_global_flags)
            if(CONAN_SYSTEM_INCLUDES)
                include_directories(SYSTEM ${CONAN_INCLUDE_DIRS}
                                           "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                           "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELWITHDEBINFO}>"
                                           "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_MINSIZEREL}>"
                                           "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
            else()
                include_directories(${CONAN_INCLUDE_DIRS}
                                    "$<$<CONFIG:Release>:${CONAN_INCLUDE_DIRS_RELEASE}>"
                                    "$<$<CONFIG:RelWithDebInfo>:${CONAN_INCLUDE_DIRS_RELWITHDEBINFO}>"
                                    "$<$<CONFIG:MinSizeRel>:${CONAN_INCLUDE_DIRS_MINSIZEREL}>"
                                    "$<$<CONFIG:Debug>:${CONAN_INCLUDE_DIRS_DEBUG}>")
            endif()

            link_directories(${CONAN_LIB_DIRS})

            conan_find_libraries_abs_path("${CONAN_LIBS_DEBUG}" "${CONAN_LIB_DIRS_DEBUG}"
                                          CONAN_LIBS_DEBUG)
            conan_find_libraries_abs_path("${CONAN_LIBS_RELEASE}" "${CONAN_LIB_DIRS_RELEASE}"
                                          CONAN_LIBS_RELEASE)
            conan_find_libraries_abs_path("${CONAN_LIBS_RELWITHDEBINFO}" "${CONAN_LIB_DIRS_RELWITHDEBINFO}"
                                          CONAN_LIBS_RELWITHDEBINFO)
            conan_find_libraries_abs_path("${CONAN_LIBS_MINSIZEREL}" "${CONAN_LIB_DIRS_MINSIZEREL}"
                                          CONAN_LIBS_MINSIZEREL)

            add_compile_options(${CONAN_DEFINES}
                                "$<$<CONFIG:Debug>:${CONAN_DEFINES_DEBUG}>"
                                "$<$<CONFIG:Release>:${CONAN_DEFINES_RELEASE}>"
                                "$<$<CONFIG:RelWithDebInfo>:${CONAN_DEFINES_RELWITHDEBINFO}>"
                                "$<$<CONFIG:MinSizeRel>:${CONAN_DEFINES_MINSIZEREL}>")

            conan_set_flags("")
            conan_set_flags("_RELEASE")
            conan_set_flags("_DEBUG")

        endmacro()
    """)

    conan_target_link_libraries = textwrap.dedent("""
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
    """)

    conan_include_build_modules = textwrap.dedent("""
        macro(conan_include_build_modules)
            if(CMAKE_BUILD_TYPE)
                if(${CMAKE_BUILD_TYPE} MATCHES "Debug")
                    set(CONAN_BUILD_MODULES_PATHS ${CONAN_BUILD_MODULES_PATHS_DEBUG} ${CONAN_BUILD_MODULES_PATHS})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "Release")
                    set(CONAN_BUILD_MODULES_PATHS ${CONAN_BUILD_MODULES_PATHS_RELEASE} ${CONAN_BUILD_MODULES_PATHS})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "RelWithDebInfo")
                    set(CONAN_BUILD_MODULES_PATHS ${CONAN_BUILD_MODULES_PATHS_RELWITHDEBINFO} ${CONAN_BUILD_MODULES_PATHS})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "MinSizeRel")
                    set(CONAN_BUILD_MODULES_PATHS ${CONAN_BUILD_MODULES_PATHS_MINSIZEREL} ${CONAN_BUILD_MODULES_PATHS})
                endif()
            endif()

            foreach(_BUILD_MODULE_PATH ${CONAN_BUILD_MODULES_PATHS})
                include(${_BUILD_MODULE_PATH})
            endforeach()
        endmacro()
    """)

    conan_set_vs_runtime = textwrap.dedent("""
        macro(conan_set_vs_runtime)
            if(CONAN_LINK_RUNTIME)
                conan_get_policy(CMP0091 policy_0091)
                if(policy_0091 STREQUAL "NEW")
                    if(CONAN_LINK_RUNTIME MATCHES "MTd")
                        set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreadedDebug")
                    elseif(CONAN_LINK_RUNTIME MATCHES "MDd")
                        set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreadedDebugDLL")
                    elseif(CONAN_LINK_RUNTIME MATCHES "MT")
                        set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
                    elseif(CONAN_LINK_RUNTIME MATCHES "MD")
                        set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreadedDLL")
                    endif()
                else()
                    foreach(flag CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
                                 CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
                                 CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL)
                        if(DEFINED ${flag})
                            string(REPLACE "/MD" ${CONAN_LINK_RUNTIME} ${flag} "${${flag}}")
                        endif()
                    endforeach()
                    foreach(flag CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG)
                        if(DEFINED ${flag})
                            string(REPLACE "/MDd" ${CONAN_LINK_RUNTIME} ${flag} "${${flag}}")
                        endif()
                    endforeach()
                endif()
            endif()
        endmacro()
    """)

    conan_set_vs_runtime_preserve_build_type = textwrap.dedent("""
        macro(conan_set_vs_runtime)
            # This conan_set_vs_runtime is MORE opinionated than the regular one. It will
            # Leave the defaults MD (MDd) or replace them with MT (MTd) but taking into account the
            # debug, forcing MXd for debug builds. It will generate MSVCRT warnings if the dependencies
            # are installed with "conan install" and the wrong build type.
            conan_get_policy(CMP0091 policy_0091)
            if(CONAN_LINK_RUNTIME MATCHES "MT")
                if(policy_0091 STREQUAL "NEW")
                    if(CMAKE_BUILD_TYPE STREQUAL "Release" OR
                       CMAKE_BUILD_TYPE STREQUAL "RelWithDebInfo" OR
                       CMAKE_BUILD_TYPE STREQUAL "MinSizeRel")
                        if (CMAKE_MSVC_RUNTIME_LIBRARY STREQUAL "MultiThreadedDLL")
                            set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreaded")
                        endif()
                    elseif(CMAKE_BUILD_TYPE STREQUAL "Debug")
                        if (CMAKE_MSVC_RUNTIME_LIBRARY STREQUAL "MultiThreadedDebugDLL")
                            set(CMAKE_MSVC_RUNTIME_LIBRARY "MultiThreadedDebug")
                        endif()
                    endif()
                else()
                    foreach(flag CMAKE_C_FLAGS_RELEASE CMAKE_CXX_FLAGS_RELEASE
                                    CMAKE_C_FLAGS_RELWITHDEBINFO CMAKE_CXX_FLAGS_RELWITHDEBINFO
                                    CMAKE_C_FLAGS_MINSIZEREL CMAKE_CXX_FLAGS_MINSIZEREL)
                        if(DEFINED ${flag})
                            string(REPLACE "/MD" "/MT" ${flag} "${${flag}}")
                        endif()
                    endforeach()
                    foreach(flag CMAKE_C_FLAGS_DEBUG CMAKE_CXX_FLAGS_DEBUG)
                        if(DEFINED ${flag})
                            string(REPLACE "/MDd" "/MTd" ${flag} "${${flag}}")
                        endif()
                    endforeach()
                endif()
            endif()
        endmacro()
    """)

    conan_set_find_paths = textwrap.dedent("""
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
    """)

    conan_set_find_paths_multi = textwrap.dedent("""
        macro(conan_set_find_paths)
            if(CMAKE_BUILD_TYPE)
                MESSAGE("BUILD TYPE: ${CMAKE_BUILD_TYPE}")
                if(${CMAKE_BUILD_TYPE} MATCHES "Debug")
                    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_PREFIX_PATH})
                    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_DEBUG} ${CMAKE_MODULE_PATH})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "Release")
                    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_PREFIX_PATH})
                    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_RELEASE} ${CMAKE_MODULE_PATH})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "RelWithDebInfo")
                    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_RELWITHDEBINFO} ${CMAKE_PREFIX_PATH})
                    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_RELWITHDEBINFO} ${CMAKE_MODULE_PATH})
                elseif(${CMAKE_BUILD_TYPE} MATCHES "MinSizeRel")
                    set(CMAKE_PREFIX_PATH ${CONAN_CMAKE_MODULE_PATH_MINSIZEREL} ${CMAKE_PREFIX_PATH})
                    set(CMAKE_MODULE_PATH ${CONAN_CMAKE_MODULE_PATH_MINSIZEREL} ${CMAKE_MODULE_PATH})
                endif()
            endif()
        endmacro()
    """)

    conan_set_find_library_paths = textwrap.dedent("""
        macro(conan_set_find_library_paths)
            # CMAKE_INCLUDE_PATH, CMAKE_LIBRARY_PATH does not have Debug/Release config, but there are variables
            # CONAN_INCLUDE_DIRS_DEBUG/RELEASE CONAN_LIB_DIRS_DEBUG/RELEASE to be used by the consumer
            # For find_library
            set(CMAKE_INCLUDE_PATH ${CONAN_INCLUDE_DIRS} ${CMAKE_INCLUDE_PATH})
            set(CMAKE_LIBRARY_PATH ${CONAN_LIB_DIRS} ${CMAKE_LIBRARY_PATH})
        endmacro()
    """)

    apple_frameworks_macro = textwrap.dedent("""
        macro(conan_find_apple_frameworks FRAMEWORKS_FOUND FRAMEWORKS SUFFIX BUILD_TYPE)
            if(APPLE)
                if(CMAKE_BUILD_TYPE)
                    set(_BTYPE ${CMAKE_BUILD_TYPE})
                elseif(NOT BUILD_TYPE STREQUAL "")
                    set(_BTYPE ${BUILD_TYPE})
                endif()
                if(_BTYPE)
                    if(${_BTYPE} MATCHES "Debug|_DEBUG")
                        set(CONAN_FRAMEWORKS${SUFFIX} ${CONAN_FRAMEWORKS${SUFFIX}_DEBUG} ${CONAN_FRAMEWORKS${SUFFIX}})
                        set(CONAN_FRAMEWORK_DIRS${SUFFIX} ${CONAN_FRAMEWORK_DIRS${SUFFIX}_DEBUG} ${CONAN_FRAMEWORK_DIRS${SUFFIX}})
                    elseif(${_BTYPE} MATCHES "Release|_RELEASE")
                        set(CONAN_FRAMEWORKS${SUFFIX} ${CONAN_FRAMEWORKS${SUFFIX}_RELEASE} ${CONAN_FRAMEWORKS${SUFFIX}})
                        set(CONAN_FRAMEWORK_DIRS${SUFFIX} ${CONAN_FRAMEWORK_DIRS${SUFFIX}_RELEASE} ${CONAN_FRAMEWORK_DIRS${SUFFIX}})
                    elseif(${_BTYPE} MATCHES "RelWithDebInfo|_RELWITHDEBINFO")
                        set(CONAN_FRAMEWORKS${SUFFIX} ${CONAN_FRAMEWORKS${SUFFIX}_RELWITHDEBINFO} ${CONAN_FRAMEWORKS${SUFFIX}})
                        set(CONAN_FRAMEWORK_DIRS${SUFFIX} ${CONAN_FRAMEWORK_DIRS${SUFFIX}_RELWITHDEBINFO} ${CONAN_FRAMEWORK_DIRS${SUFFIX}})
                    elseif(${_BTYPE} MATCHES "MinSizeRel|_MINSIZEREL")
                        set(CONAN_FRAMEWORKS${SUFFIX} ${CONAN_FRAMEWORKS${SUFFIX}_MINSIZEREL} ${CONAN_FRAMEWORKS${SUFFIX}})
                        set(CONAN_FRAMEWORK_DIRS${SUFFIX} ${CONAN_FRAMEWORK_DIRS${SUFFIX}_MINSIZEREL} ${CONAN_FRAMEWORK_DIRS${SUFFIX}})
                    endif()
                endif()
                foreach(_FRAMEWORK ${FRAMEWORKS})
                    # https://cmake.org/pipermail/cmake-developers/2017-August/030199.html
                    find_library(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND NAMES ${_FRAMEWORK} PATHS ${CONAN_FRAMEWORK_DIRS${SUFFIX}} CMAKE_FIND_ROOT_PATH_BOTH)
                    if(CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND)
                        list(APPEND ${FRAMEWORKS_FOUND} ${CONAN_FRAMEWORK_${_FRAMEWORK}_FOUND})
                    else()
                        message(FATAL_ERROR "Framework library ${_FRAMEWORK} not found in paths: ${CONAN_FRAMEWORK_DIRS${SUFFIX}}")
                    endif()
                endforeach()
            endif()
        endmacro()
    """)


_cmake_common_macros = "\n".join([
    CMakeCommonMacros.conan_message,
    CMakeCommonMacros.conan_get_policy,
    CMakeCommonMacros.conan_find_libraries_abs_path,
    CMakeCommonMacros.conan_package_library_targets,
    CMakeCommonMacros.conan_set_libcxx,
    CMakeCommonMacros.conan_set_std,
    CMakeCommonMacros.conan_set_rpath,
    CMakeCommonMacros.conan_set_fpic,
    CMakeCommonMacros.conan_output_dirs_setup,
    CMakeCommonMacros.conan_split_version,
    CMakeCommonMacros.conan_error_compiler_version,
    "set(_CONAN_CURRENT_DIR ${CMAKE_CURRENT_LIST_DIR})",
    CMakeCommonMacros.conan_get_compiler,
    CMakeCommonMacros.check_compiler_version,
    CMakeCommonMacros.conan_check_compiler,
    CMakeCommonMacros.conan_set_flags,
    CMakeCommonMacros.conan_global_flags,
    CMakeCommonMacros.conan_target_link_libraries,
    CMakeCommonMacros.conan_include_build_modules,
])


def _conan_basic_setup_common(addtional_macros, cmake_multi=False):
    output_dirs_section = """
    if(NOT ARGUMENTS_NO_OUTPUT_DIRS)
        conan_message(STATUS "Conan: Adjusting output directories")
        conan_output_dirs_setup()
    endif()"""

    output_dirs_multi_section = """
    if(ARGUMENTS_NO_OUTPUT_DIRS)
        conan_message(WARNING "Conan: NO_OUTPUT_DIRS has no effect with cmake_multi generator")
    endif()"""

    main_section = """
macro(conan_basic_setup)
    set(options TARGETS NO_OUTPUT_DIRS SKIP_RPATH KEEP_RPATHS SKIP_STD SKIP_FPIC)
    cmake_parse_arguments(ARGUMENTS "${options}" "${oneValueArgs}" "${multiValueArgs}" ${ARGN} )

    if(CONAN_EXPORTED)
        conan_message(STATUS "Conan: called by CMake conan helper")
    endif()

    if(CONAN_IN_LOCAL_CACHE)
        conan_message(STATUS "Conan: called inside local cache")
    endif()
%%OUTPUT_DIRS_SECTION%%

    if(NOT ARGUMENTS_TARGETS)
        conan_message(STATUS "Conan: Using cmake global configuration")
        conan_global_flags()
    else()
        conan_message(STATUS "Conan: Using cmake targets configuration")
        conan_define_targets()
    endif()

    if(ARGUMENTS_SKIP_RPATH)
        # Change by "DEPRECATION" or "SEND_ERROR" when we are ready
        conan_message(WARNING "Conan: SKIP_RPATH is deprecated, it has been renamed to KEEP_RPATHS")
    endif()

    if(NOT ARGUMENTS_SKIP_RPATH AND NOT ARGUMENTS_KEEP_RPATHS)
        # Parameter has renamed, but we keep the compatibility with old SKIP_RPATH
        conan_set_rpath()
    endif()

    if(NOT ARGUMENTS_SKIP_STD)
        conan_set_std()
    endif()

    if(NOT ARGUMENTS_SKIP_FPIC)
        conan_set_fpic()
    endif()

    conan_check_compiler()
    conan_set_libcxx()
    conan_set_vs_runtime()
    conan_set_find_paths()
    conan_include_build_modules()
    %%INVOKE_MACROS%%
endmacro()
"""
    result = main_section.replace("%%OUTPUT_DIRS_SECTION%%",
                                  output_dirs_multi_section if cmake_multi else output_dirs_section)
    result = result.replace("%%INVOKE_MACROS%%", "\n    ".join(addtional_macros))
    return result


cmake_macros = "\n".join([
    _conan_basic_setup_common(["conan_set_find_library_paths()"]),
    CMakeCommonMacros.conan_set_find_paths,
    CMakeCommonMacros.conan_set_find_library_paths,
    CMakeCommonMacros.conan_set_vs_runtime,
    textwrap.dedent("""
        macro(conan_flags_setup)
            # Macro maintained for backwards compatibility
            conan_set_find_library_paths()
            conan_global_flags()
            conan_set_rpath()
            conan_set_vs_runtime()
            conan_set_libcxx()
        endmacro()
        """),
    _cmake_common_macros])


cmake_macros_multi = "\n".join([
    textwrap.dedent("""
        ### load generated conanbuildinfo files.
        foreach(_name release debug minsizerel relwithdebinfo)
            if(EXISTS ${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_${_name}.cmake)
                include(${CMAKE_CURRENT_LIST_DIR}/conanbuildinfo_${_name}.cmake)
            endif()
        endforeach()
        """),
    CMakeCommonMacros.conan_set_vs_runtime_preserve_build_type,
    CMakeCommonMacros.conan_set_find_paths_multi,
    _conan_basic_setup_common([], cmake_multi=True),
    _cmake_common_macros])
