import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate
from conan.tools.cmake.cmakedeps.utils import DepsCppCmake
from conans.errors import ConanException

"""

foo-release-x86_64-data.cmake

"""

class ConfigDataTemplate(CMakeDepsFileTemplate):

    def __init__(self, req, configuration, arch):
        super(ConfigDataTemplate, self).__init__(req, configuration)
        self.arch = arch

    @property
    def filename(self):
        data_fname = "{}-{}".format(self.pkg_name, self.configuration.lower())
        if self.arch:
            data_fname += "-{}".format(self.arch)
        data_fname += "-data.cmake"
        return data_fname

    @property
    def context(self):
        global_cpp = self.get_global_cpp_cmake()
        components_cpp = self.get_required_components_cpp()
        components_names = " ".join([comp_findname for comp_findname, _, _ in
                                     reversed(components_cpp)])
        dependency_names = self.get_dependency_names()
        return {"global_cpp": global_cpp,
                "pkg_name": self.pkg_name,
                "package_folder": self.package_folder,
                "config_suffix": self.config_suffix,
                "components_names": components_names,
                "components_cpp": components_cpp,
                "dependency_names": " ".join(dependency_names)}

    @property
    def template(self):
        # This will be at: XXX-release-data.cmake
        ret = textwrap.dedent("""\
              ########### AGGREGATED COMPONENTS AND DEPENDENCIES FOR THE MULTI CONFIG #####################
              #############################################################################################

              set({{ pkg_name }}_COMPONENT_NAMES {{ '${'+ pkg_name }}_COMPONENT_NAMES} {{ components_names }})
              list(REMOVE_DUPLICATES {{ pkg_name }}_COMPONENT_NAMES)
              set({{ pkg_name }}_FIND_DEPENDENCY_NAMES {{ '${'+ pkg_name }}_FIND_DEPENDENCY_NAMES} {{ dependency_names }})
              list(REMOVE_DUPLICATES {{ pkg_name }}_FIND_DEPENDENCY_NAMES)

              ########### VARIABLES #######################################################################
              #############################################################################################

              set({{ pkg_name }}_PACKAGE_FOLDER{{ config_suffix }} "{{  package_folder }}")
              set({{ pkg_name }}_INCLUDE_DIRS{{ config_suffix }} {{ global_cpp.include_paths }})
              set({{ pkg_name }}_RES_DIRS{{ config_suffix }} {{ global_cpp.res_paths }})
              set({{ pkg_name }}_DEFINITIONS{{ config_suffix }} {{ global_cpp.defines }})
              set({{ pkg_name }}_SHARED_LINK_FLAGS{{ config_suffix }} {{ global_cpp.sharedlinkflags_list }})
              set({{ pkg_name }}_EXE_LINK_FLAGS{{ config_suffix }} {{ global_cpp.exelinkflags_list }})
              set({{ pkg_name }}_COMPILE_DEFINITIONS{{ config_suffix }} {{ global_cpp.compile_definitions }})
              set({{ pkg_name }}_COMPILE_OPTIONS_C{{ config_suffix }} {{ global_cpp.cflags_list }})
              set({{ pkg_name }}_COMPILE_OPTIONS_CXX{{ config_suffix }} {{ global_cpp.cxxflags_list}})
              set({{ pkg_name }}_LIB_DIRS{{ config_suffix }} {{ global_cpp.lib_paths }})
              set({{ pkg_name }}_LIBS{{ config_suffix }} {{ global_cpp.libs }})
              set({{ pkg_name }}_SYSTEM_LIBS{{ config_suffix }} {{ global_cpp.system_libs }})
              set({{ pkg_name }}_FRAMEWORK_DIRS{{ config_suffix }} {{ global_cpp.framework_paths }})
              set({{ pkg_name }}_FRAMEWORKS{{ config_suffix }} {{ global_cpp.frameworks }})
              set({{ pkg_name }}_BUILD_MODULES_PATHS{{ config_suffix }} {{ global_cpp.build_modules_paths }})
              set({{ pkg_name }}_BUILD_DIRS{{ config_suffix }} {{ global_cpp.build_paths }})

              set({{ pkg_name }}_COMPONENTS{{ config_suffix }} {{ components_names }})

              {%- for comp_name, comp_alias, cpp in components_cpp %}

              ########### COMPONENT {{ comp_name }} VARIABLES #############################################
              set({{ pkg_name }}_PACKAGE_FOLDER{{ config_suffix }} "{{ package_folder }}")
              set({{ pkg_name }}_{{ comp_name }}_ALIAS "{{ comp_alias }}")

              set({{ pkg_name }}_{{ comp_name }}_INCLUDE_DIRS{{ config_suffix }} {{ cpp.include_paths }})
              set({{ pkg_name }}_{{ comp_name }}_LIB_DIRS{{ config_suffix }} {{ cpp.lib_paths }})
              set({{ pkg_name }}_{{ comp_name }}_RES_DIRS{{ config_suffix }} {{ cpp.res_paths }})
              set({{ pkg_name }}_{{ comp_name }}_DEFINITIONS{{ config_suffix }} {{ cpp.defines }})
              set({{ pkg_name }}_{{ comp_name }}_COMPILE_DEFINITIONS{{ config_suffix }} {{ cpp.compile_definitions }})
              set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_C{{ config_suffix }} "{{ cpp.cflags_list }}")
              set({{ pkg_name }}_{{ comp_name }}_COMPILE_OPTIONS_CXX{{ config_suffix }} "{{ cpp.cxxflags_list }}")
              set({{ pkg_name }}_{{ comp_name }}_LIBS{{ config_suffix }} {{ cpp.libs }})
              set({{ pkg_name }}_{{ comp_name }}_SYSTEM_LIBS{{ config_suffix }} {{ cpp.system_libs }})
              set({{ pkg_name }}_{{ comp_name }}_FRAMEWORK_DIRS{{ config_suffix }} {{ cpp.framework_paths }})
              set({{ pkg_name }}_{{ comp_name }}_FRAMEWORKS{{ config_suffix }} {{ cpp.frameworks }})
              set({{ pkg_name }}_{{ comp_name }}_DEPENDENCIES{{ config_suffix }} {{ cpp.public_deps }})
              set({{ pkg_name }}_{{ comp_name }}_LINKER_FLAGS{{ config_suffix }}
                      $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,SHARED_LIBRARY>:{{ cpp.sharedlinkflags_list }}>
                      $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,MODULE_LIBRARY>:{{ cpp.sharedlinkflags_list }}>
                      $<$<STREQUAL:$<TARGET_PROPERTY:TYPE>,EXECUTABLE>:{{ cpp.exelinkflags_list }}>
              )
              {%- endfor %}
          """)
        return ret

    def get_global_cpp_cmake(self):
        global_cppinfo = self.conanfile.new_cpp_info.copy()
        global_cppinfo.aggregate_components()
        pfolder_var_name = "{}_PACKAGE_FOLDER{}".format(self.pkg_name, self.config_suffix)
        return DepsCppCmake(global_cppinfo, pfolder_var_name)

    def get_required_components_cpp(self):
        """Returns a list of (component_name, DepsCppCMake)"""
        ret = []
        sorted_comps = self.conanfile.new_cpp_info.get_sorted_components()

        for comp_name, comp in sorted_comps.items():
            pfolder_var_name = "{}_PACKAGE_FOLDER{}".format(self.conanfile.ref.name,
                                                            self.config_suffix)
            deps_cpp_cmake = DepsCppCmake(comp, pfolder_var_name)
            public_comp_deps = []
            for require in comp.requires:
                if "::" in require:  # Points to a component of a different package
                    pkg, cmp_name = require.split("::")
                    public_comp_deps.append("{}::{}".format(pkg, cmp_name))
                else:  # Points to a component of same package
                    public_comp_deps.append("{}::{}".format(self.pkg_name, require))
            deps_cpp_cmake.public_deps = " ".join(public_comp_deps)
            component_alias = self.get_component_rename(comp_name)
            ret.append((comp_name, component_alias, deps_cpp_cmake))
        ret.reverse()
        return ret

    def get_component_rename(self, comp_name):
        if comp_name not in self.conanfile.new_cpp_info.components:
            if self.conanfile.ref.name == comp_name:  # foo::foo might be referencing the root cppinfo
                return comp_name
            raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                                 "package requirement".format(name=self.conanfile.ref.name,
                                                              cname=comp_name))
        ret = self.conanfile.new_cpp_info.components[comp_name].get_property("cmake_target_name",
                                                                             "CMakeDeps")
        if not ret:
            ret = self.conanfile.cpp_info.components[comp_name].get_name("cmake_find_package_multi",
                                                              default_name=False)
        return ret or comp_name
