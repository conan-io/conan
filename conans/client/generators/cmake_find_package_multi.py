from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package import find_dependency_lines
from conans.client.generators.cmake_find_package_common import find_libraries, \
    generic_common_set_vars
from conans.model import Generator


class CMakeFindPackageMultiGenerator(Generator):
    template = generic_common_set_vars + """
    
# Load the debug and release library finders
get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
file(GLOB CONFIG_FILES "${{_DIR}}/Find{name}-*.cmake")

if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
    # Target approach
    if(NOT TARGET {name}::{name})
        add_library({name}::{name} INTERFACE IMPORTED)
    endif()
endif()

foreach(f ${{CONFIG_FILES}})
  include(${{f}})
endforeach()

include(SelectLibraryConfigurations)
select_library_configurations({name})

# CMake doesn't have a mechanism to select also the right include directories, assume we can use any of them or use
# the variable _DEBUG or _RELEASE
set({name}_INCLUDE_DIRS ${{{name}_INCLUDE_DIRS_RELEASE}} ${{{name}_INCLUDE_DIRS_DEBUG}})

if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
    {target_props_block}
    {find_dependencies_block}
endif()

"""

    target_properties = """
    # Assign target properties
    set_property(TARGET {name}::{name} 
                 PROPERTY INTERFACE_LINK_LIBRARIES 
                     $<$<CONFIG:Release>:${{{name}_LIBRARIES_TARGETS_RELEASE}} ${{{name}_LINKER_FLAGS_RELEASE_LIST}}>
                     $<$<CONFIG:RelWithDebInfo>:${{{name}_LIBRARIES_TARGETS_RELEASE}} ${{{name}_LINKER_FLAGS_RELEASE_LIST}}>
                     $<$<CONFIG:MinSizeRel>:${{{name}_LIBRARIES_TARGETS_RELEASE}} ${{{name}_LINKER_FLAGS_RELEASE_LIST}}>
                     $<$<CONFIG:Debug>:${{{name}_LIBRARIES_TARGETS_DEBUG}} ${{{name}_LINKER_FLAGS_DEBUG_LIST}}>)
    set_property(TARGET {name}::{name} 
                 PROPERTY INTERFACE_INCLUDE_DIRECTORIES 
                     $<$<CONFIG:Release>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                     $<$<CONFIG:RelWithDebInfo>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                     $<$<CONFIG:MinSizeRel>:${{{name}_INCLUDE_DIRS_RELEASE}}>
                     $<$<CONFIG:Debug>:${{{name}_INCLUDE_DIRS_DEBUG}}>)
    set_property(TARGET {name}::{name} 
                 PROPERTY INTERFACE_COMPILE_DEFINITIONS 
                     $<$<CONFIG:Release>:${{{name}_COMPILE_DEFINITIONS_RELEASE}}>
                     $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_DEFINITIONS_RELEASE}}>
                     $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_DEFINITIONS_RELEASE}}>
                     $<$<CONFIG:Debug>:${{{name}_COMPILE_DEFINITIONS_DEBUG}}>)
    set_property(TARGET {name}::{name} 
                 PROPERTY INTERFACE_COMPILE_OPTIONS 
                     $<$<CONFIG:Release>:${{{name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                     $<$<CONFIG:RelWithDebInfo>:${{{name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                     $<$<CONFIG:MinSizeRel>:${{{name}_COMPILE_OPTIONS_RELEASE_LIST}}>
                     $<$<CONFIG:Debug>:${{{name}_COMPILE_OPTIONS_DEBUG_LIST}}>) 
    """

    @property
    def filename(self):
        pass

    @property
    def content(self):
        ret = {}
        build_type = self.conanfile.settings.get_safe("build_type")
        build_type_suffix = "_{}".format(build_type.upper()) if build_type else ""
        for depname, cpp_info in self.deps_build_info.dependencies:
            deps = DepsCppCmake(cpp_info)
            ret["Find%s.cmake" % depname] = self._find_for_dep(depname, cpp_info)

            find_lib = find_libraries.format(name=depname, deps=deps,
                                             build_type_suffix=build_type_suffix)
            ret["Find{}-{}.cmake".format(depname, build_type)] = find_lib
        return ret

    def _build_type_suffix(self, build_type):
        return

    def _find_for_dep(self, name, cpp_info):
        deps = DepsCppCmake(cpp_info)
        lines = []
        if cpp_info.public_deps:
            lines = find_dependency_lines(name, cpp_info)

        targets_props = self.target_properties.format(name=name, deps=deps)

        tmp = self.template.format(name=name, deps=deps,
                                   version=cpp_info.version,
                                   find_dependencies_block="\n".join(lines),
                                   target_props_block=targets_props)

        return tmp
