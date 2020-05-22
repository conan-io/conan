import textwrap

from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package_common import (find_transitive_dependencies,
                                                                target_template,
                                                                CMakeFindPackageCommonMacros)
from conans.client.generators.cmake_multi import extend
from conans.model import Generator


class CMakeFindPackageMultiGenerator(Generator):
    config_template = textwrap.dedent("""
        {macros_and_functions}

        # Requires CMake > 3.0
        if(${{CMAKE_VERSION}} VERSION_LESS "3.0")
           message(FATAL_ERROR "The 'cmake_find_package_multi' generator only works with CMake > 3.0" )
        endif()

        include(${{CMAKE_CURRENT_LIST_DIR}}/{name}Targets.cmake)

        {target_props_block}
        {find_dependencies_block}
        """)

    targets_template = textwrap.dedent("""
        if(NOT TARGET {name}::{name})
            add_library({name}::{name} INTERFACE IMPORTED)
        endif()

        # Load the debug and release library finders
        get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
        file(GLOB CONFIG_FILES "${{_DIR}}/{name}Target-*.cmake")

        foreach(f ${{CONFIG_FILES}})
          include(${{f}})
        endforeach()

        """)

    target_properties = """
# Assign target properties
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_LINK_LIBRARIES
                 $<$<CONFIG:Release>:${{{name}_LIBRARIES_TARGETS_RELEASE}} ${{{name}_LINKER_FLAGS_RELEASE_LIST}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_LIBRARIES_TARGETS_RELWITHDEBINFO}} ${{{name}_LINKER_FLAGS_RELWITHDEBINFO_LIST}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_LIBRARIES_TARGETS_MINSIZEREL}} ${{{name}_LINKER_FLAGS_MINSIZEREL_LIST}}>
                 $<$<CONFIG:Debug>:${{{name}_LIBRARIES_TARGETS_DEBUG}} ${{{name}_LINKER_FLAGS_DEBUG_LIST}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_INCLUDE_DIRECTORIES
                 $<$<CONFIG:Release>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_INCLUDE_DIRS_RELWITHDEBINFO}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_INCLUDE_DIRS_MINSIZEREL}}>
                 $<$<CONFIG:Debug>:${{{name}_INCLUDE_DIRS_DEBUG}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_COMPILE_DEFINITIONS
                 $<$<CONFIG:Release>:${{{name}_COMPILE_DEFINITIONS_RELEASE}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_DEFINITIONS_RELWITHDEBINFO}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_DEFINITIONS_MINSIZEREL}}>
                 $<$<CONFIG:Debug>:${{{name}_COMPILE_DEFINITIONS_DEBUG}}>)
set_property(TARGET {name}::{name}
             PROPERTY INTERFACE_COMPILE_OPTIONS
                 $<$<CONFIG:Release>:${{{name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                 $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_OPTIONS_RELWITHDEBINFO_LIST}}>
                 $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_OPTIONS_MINSIZEREL_LIST}}>
                 $<$<CONFIG:Debug>:${{{name}_COMPILE_OPTIONS_DEBUG_LIST}}>)
    """

    # https://gitlab.kitware.com/cmake/cmake/blob/master/Modules/BasicConfigVersion-SameMajorVersion.cmake.in
    config_version_template = textwrap.dedent("""
        set(PACKAGE_VERSION "{version}")

        if(PACKAGE_VERSION VERSION_LESS PACKAGE_FIND_VERSION)
            set(PACKAGE_VERSION_COMPATIBLE FALSE)
        else()
            if("{version}" MATCHES "^([0-9]+)\\\\.")
                set(CVF_VERSION_MAJOR "${{CMAKE_MATCH_1}}")
            else()
                set(CVF_VERSION_MAJOR "{version}")
            endif()

            if(PACKAGE_FIND_VERSION_MAJOR STREQUAL CVF_VERSION_MAJOR)
                set(PACKAGE_VERSION_COMPATIBLE TRUE)
            else()
                set(PACKAGE_VERSION_COMPATIBLE FALSE)
            endif()

            if(PACKAGE_FIND_VERSION STREQUAL PACKAGE_VERSION)
                set(PACKAGE_VERSION_EXACT TRUE)
            endif()
        endif()
        """)

    @property
    def filename(self):
        return None

    @property
    def content(self):
        ret = {}
        build_type = str(self.conanfile.settings.build_type)
        build_type_suffix = "_{}".format(build_type.upper()) if build_type else ""
        for _, cpp_info in self.deps_build_info.dependencies:
            depname = cpp_info.get_name("cmake_find_package_multi")
            public_deps_names = [self.deps_build_info[dep].get_name("cmake_find_package_multi")
                                 for dep in cpp_info.public_deps]
            ret["{}Config.cmake".format(depname)] = self._config(depname, cpp_info.version,
                                                                 public_deps_names)
            ret["{}ConfigVersion.cmake".format(depname)] = self.config_version_template.\
                format(version=cpp_info.version)
            ret["{}Targets.cmake".format(depname)] = self.targets_template.format(name=depname)

            # If any config matches the build_type one, add it to the cpp_info
            dep_cpp_info = extend(cpp_info, build_type.lower())
            deps = DepsCppCmake(dep_cpp_info)
            deps_names = ";".join(["{n}::{n}".format(n=n) for n in public_deps_names])
            find_lib = target_template.format(name=depname, deps=deps,
                                              build_type_suffix=build_type_suffix,
                                              deps_names=deps_names)
            ret["{}Target-{}.cmake".format(depname, build_type.lower())] = find_lib
        return ret

    def _config(self, name, version, public_deps_names):
        # Builds the XXXConfig.cmake file for one package

        # The common macros
        macros_and_functions = "\n".join([
            CMakeFindPackageCommonMacros.conan_message,
            CMakeFindPackageCommonMacros.apple_frameworks_macro,
            CMakeFindPackageCommonMacros.conan_package_library_targets,
        ])

        # Define the targets properties
        targets_props = self.target_properties.format(name=name)

        # The find_dependencies_block
        find_dependencies_block = ""
        if public_deps_names:
            # Here we are generating only Config files, so do not search for FindXXX modules
            find_dependencies_block = find_transitive_dependencies(public_deps_names,
                                                                   find_modules=False)

        tmp = self.config_template.format(name=name, version=version,
                                          target_props_block=targets_props,
                                          find_dependencies_block=find_dependencies_block,
                                          macros_and_functions=macros_and_functions)
        return tmp
