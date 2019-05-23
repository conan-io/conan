from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_find_package import find_dependency_lines
from conans.client.generators.cmake_find_package_common import target_template
from conans.model import Generator


class CMakeFindPackageMultiGenerator(Generator):
    config_xxx_template = """

# Requires CMake > 3.0
if(${{CMAKE_VERSION}} VERSION_LESS "3.0")
   message(FATAL_ERROR "The 'cmake_find_package_multi' only works with CMake > 3.0" )
endif()

include(${{CMAKE_CURRENT_LIST_DIR}}/{name}Targets.cmake)

{target_props_block}
{find_dependencies_block}
"""

    targets_file = """
if(NOT TARGET {name}::{name})
    add_library({name}::{name} INTERFACE IMPORTED)
endif()

# Load the debug and release library finders
get_filename_component(_DIR "${{CMAKE_CURRENT_LIST_FILE}}" PATH)
file(GLOB CONFIG_FILES "${{_DIR}}/{name}Target-*.cmake")

foreach(f ${{CONFIG_FILES}})
  include(${{f}})
endforeach()
    
"""

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
            ret["{}Config.cmake".format(depname)] = self._find_for_dep(depname, cpp_info)

            find_lib = target_template.format(name=depname, deps=deps,
                                              build_type_suffix=build_type_suffix)
            ret["{}Targets.cmake".format(depname)] = self.targets_file.format(name=depname)
            ret["{}Target-{}.cmake".format(depname, build_type.lower())] = find_lib
        return ret

    def _build_type_suffix(self, build_type):
        return

    def _find_for_dep(self, name, cpp_info):
        lines = []
        if cpp_info.public_deps:
            # Here we are generating only Config files, so do not search for FindXXX modules
            lines = find_dependency_lines(name, cpp_info, find_modules=False)

        targets_props = self.target_properties.format(name=name)

        tmp = self.config_xxx_template.format(name=name,
                                              version=cpp_info.version,
                                              find_dependencies_block="\n".join(lines),
                                              target_props_block=targets_props)

        return tmp
