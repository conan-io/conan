from conans.client.generators.cmake import DepsCppCmake
from conans.client.generators.cmake_common import include_build_modules
from conans.client.generators.cmake_find_package_common import target_template
from conans.model import Generator

find_package_header = """
include(FindPackageHandleStandardArgs)

message(STATUS "Conan: Using autogenerated Find{name}.cmake")
# Global approach
set({name}_FOUND 1)
set({name}_VERSION "{version}")

find_package_handle_standard_args({name} REQUIRED_VARS {name}_VERSION VERSION_VAR {name}_VERSION)
mark_as_advanced({name}_FOUND {name}_VERSION)

"""


assign_target_properties = """
    if({name}_INCLUDE_DIRS)
      set_target_properties({name}::{name} PROPERTIES INTERFACE_INCLUDE_DIRECTORIES "${{{name}_INCLUDE_DIRS}}")
    endif()
    set_property(TARGET {name}::{name} PROPERTY INTERFACE_LINK_LIBRARIES ${{{name}_LIBRARIES_TARGETS}} "${{{name}_LINKER_FLAGS_LIST}}")
    set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_DEFINITIONS ${{{name}_COMPILE_DEFINITIONS}})
    set_property(TARGET {name}::{name} PROPERTY INTERFACE_COMPILE_OPTIONS "${{{name}_COMPILE_OPTIONS_LIST}}")
"""


class CMakeFindPackageGenerator(Generator):
    template = """
{find_package_header_block}
{find_libraries_block}
if(NOT ${{CMAKE_VERSION}} VERSION_LESS "3.0")
    # Target approach
    if(NOT TARGET {name}::{name})
        add_library({name}::{name} INTERFACE IMPORTED)
        {assign_target_properties_block}
        {find_dependencies_block}
    endif()
endif()

set(CMAKE_MODULE_PATH {build_paths} ${{CMAKE_MODULE_PATH}} ${{CMAKE_CURRENT_LIST_DIR}})
set(CMAKE_PREFIX_PATH {build_paths} ${{CMAKE_PREFIX_PATH}} ${{CMAKE_CURRENT_LIST_DIR}})
"""

    @property
    def filename(self):
        pass

    @property
    def content(self):
        ret = {}
        for depname, cpp_info in self.deps_build_info.dependencies:
            ret["Find%s.cmake" % cpp_info.name] = self._find_for_dep(cpp_info.name, cpp_info)
        return ret

    def _find_for_dep(self, name, cpp_info):
        deps = DepsCppCmake(cpp_info)
        lines = []
        if cpp_info.public_deps:
            # Here we are generating FindXXX, so find_modules=True
            lines = find_dependency_lines(name, cpp_info, find_modules=True)
        find_package_header_block = find_package_header.format(name=name, version=cpp_info.version)
        find_libraries_block = target_template.format(name=name, deps=deps, build_type_suffix="")
        target_props = assign_target_properties.format(name=name, deps=deps)
        contents = []
        tmp = self.template.format(name=name, deps=deps,
                                   version=cpp_info.version,
                                   find_dependencies_block="\n".join(lines),
                                   find_libraries_block=find_libraries_block,
                                   find_package_header_block=find_package_header_block,
                                   assign_target_properties_block=target_props,
                                   build_paths=deps.build_paths)
        contents.append(tmp)
        if cpp_info.build_modules_paths:
            contents.append(include_build_modules(deps.build_modules_paths))
        return "\n".join(contents)


def find_dependency_lines(name, cpp_info, find_modules):
    lines = ["", "# Library dependencies", "include(CMakeFindDependencyMacro)"]
    for dep in cpp_info.public_deps:
        def property_lines(prop):
            lib_t = "%s::%s" % (name, name)
            dep_t = "%s::%s" % (dep, dep)
            return ["get_target_property(tmp %s %s)" % (dep_t, prop),
                    "if(tmp)",
                    "  set_property(TARGET %s APPEND PROPERTY %s ${tmp})" % (lib_t, prop),
                    'endif()']

        if find_modules:
            lines.append("find_dependency(%s REQUIRED)" % dep)
        else:
            # https://github.com/conan-io/conan/issues/4994
            # https://github.com/conan-io/conan/issues/5040
            lines.append('if(${CMAKE_VERSION} VERSION_LESS "3.9.0")')
            lines.append('  find_package(%s REQUIRED NO_MODULE)' % dep)
            lines.append("else()")
            lines.append('  find_dependency(%s REQUIRED NO_MODULE)' % dep)
            lines.append("endif()")

        lines.extend(property_lines("INTERFACE_LINK_LIBRARIES"))
        lines.extend(property_lines("INTERFACE_COMPILE_DEFINITIONS"))
        lines.extend(property_lines("INTERFACE_INCLUDE_DIRECTORIES"))
    return ["    {}".format(l) for l in lines]
