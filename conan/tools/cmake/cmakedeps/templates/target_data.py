import os
import textwrap

from conan.tools.cmake.cmakedeps.templates import CMakeDepsFileTemplate, get_component_alias, \
    get_target_namespace
from conan.tools.cmake.utils import get_file_name

"""

foo-release-x86_64-data.cmake

"""


class ConfigDataTemplate(CMakeDepsFileTemplate):

    @property
    def filename(self):
        data_fname = "{}-{}".format(self.file_name, self.configuration.lower())
        if self.arch:
            data_fname += "-{}".format(self.arch)
        data_fname += "-data.cmake"
        return data_fname

    @property
    def context(self):
        global_cpp = self.get_global_cpp_cmake()
        if not self.build_modules_activated:
            global_cpp.build_modules_paths = ""

        components_cpp = self.get_required_components_cpp()
        components_renames = " ".join([component_rename for component_rename, _ in
                                       reversed(components_cpp)])
        # For the build requires, we don't care about the transitive (only runtime for the br)
        # so as the xxx-conf.cmake files won't be generated, don't include them as find_dependency
        # This is because in Conan 2.0 model, only the pure tools like CMake will be build_requires
        # for example a framework test won't be a build require but a "test/not public" require.
        dependency_filenames = self._get_dependency_filenames()
        package_folder = self.conanfile.package_folder.replace('\\', '/')\
                                                      .replace('$', '\\$').replace('"', '\\"')
        return {"global_cpp": global_cpp,
                "pkg_name": self.pkg_name,
                "package_folder": package_folder,
                "config_suffix": self.config_suffix,
                "components_renames": components_renames,
                "components_cpp": components_cpp,
                "dependency_filenames": " ".join(dependency_filenames)}

    @property
    def template(self):
        # This will be at: XXX-release-data.cmake
        ret = textwrap.dedent("""\
              ########### AGGREGATED COMPONENTS AND DEPENDENCIES FOR THE MULTI CONFIG #####################
              #############################################################################################

              set({{ pkg_name }}_COMPONENT_NAMES {{ '${'+ pkg_name }}_COMPONENT_NAMES} {{ components_renames }})
              list(REMOVE_DUPLICATES {{ pkg_name }}_COMPONENT_NAMES)
              set({{ pkg_name }}_FIND_DEPENDENCY_NAMES {{ '${'+ pkg_name }}_FIND_DEPENDENCY_NAMES} {{ dependency_filenames }})
              list(REMOVE_DUPLICATES {{ pkg_name }}_FIND_DEPENDENCY_NAMES)

              ########### VARIABLES #######################################################################
              #############################################################################################
              set({{ pkg_name }}_PACKAGE_FOLDER{{ config_suffix }} "{{ package_folder }}")
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

              set({{ pkg_name }}_COMPONENTS{{ config_suffix }} {{ components_renames }})

              {%- for comp_name, cpp in components_cpp %}

              ########### COMPONENT {{ comp_name }} VARIABLES #############################################
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
        return DepsCppCmake(global_cppinfo, pfolder_var_name, self.require)

    def get_required_components_cpp(self):
        """Returns a list of (component_name, DepsCppCMake)"""
        ret = []
        sorted_comps = self.conanfile.new_cpp_info.get_sorted_components()

        for comp_name, comp in sorted_comps.items():
            pfolder_var_name = "{}_PACKAGE_FOLDER{}".format(self.pkg_name, self.config_suffix)
            deps_cpp_cmake = DepsCppCmake(comp, pfolder_var_name)
            public_comp_deps = []
            for require in comp.requires:
                if "::" in require:  # Points to a component of a different package
                    pkg, cmp_name = require.split("::")
                    req = self.conanfile.dependencies.direct_host[pkg]
                    public_comp_deps.append("{}::{}".format(get_target_namespace(req),
                                                            get_component_alias(req, cmp_name)))
                else:  # Points to a component of same package
                    public_comp_deps.append("{}::{}".format(self.target_namespace,
                                                            get_component_alias(self.conanfile,
                                                                                 require)))
            deps_cpp_cmake.public_deps = " ".join(public_comp_deps)
            component_rename = get_component_alias(self.conanfile, comp_name)
            ret.append((component_rename, deps_cpp_cmake))
        ret.reverse()
        return ret

    def _get_dependency_filenames(self):
        if self.conanfile.is_build_context:
            return []
        ret = []
        direct_host = self.conanfile.dependencies.direct_host
        if self.conanfile.new_cpp_info.required_components:
            for dep_name, _ in self.conanfile.new_cpp_info.required_components:
                if dep_name and dep_name not in ret:  # External dep
                    req = direct_host[dep_name]
                    ret.append(get_file_name(req))
        elif direct_host:
            ret = [get_file_name(r) for r in direct_host.values()]

        return ret


class DepsCppCmake(object):

    def __init__(self, cpp_info, pfolder_var_name, require=None):

        def join_paths(paths):
            """
            Paths are doubled quoted, and escaped (but spaces)
            e.g: set(LIBFOO_INCLUDE_DIRS "/path/to/included/dir" "/path/to/included/dir2")
            """
            ret = []
            for p in paths:
                norm_path = p.replace('\\', '/').replace('$', '\\$').replace('"', '\\"')
                if os.path.isabs(p):
                    ret.append('"{}"'.format(norm_path))
                else:
                    # Prepend the {{ pkg_name }}_PACKAGE_FOLDER{{ config_suffix }}
                    ret.append('"${%s}/%s"' % (pfolder_var_name, norm_path))
            return "\n\t\t\t".join(ret)

        def join_flags(separator, values):
            # Flags have to be escaped
            return separator.join(v.replace('\\', '\\\\').replace('$', '\\$').replace('"', '\\"')
                                  for v in values)

        def join_defines(values, prefix=""):
            # Defines have to be escaped, included spaces
            return "\n\t\t\t".join('"%s%s"' % (prefix, v.replace('\\', '\\\\').replace('$', '\\$').
                                   replace('"', '\\"'))
                                   for v in values)

        def join_paths_single_var(values):
            """
            semicolon-separated list of dirs:
            e.g: set(LIBFOO_INCLUDE_DIR "/path/to/included/dir;/path/to/included/dir2")
            """
            return '"%s"' % ";".join(p.replace('\\', '/').replace('$', '\\$') for p in values)

        self.include_paths = join_paths(cpp_info.includedirs)
        if require and not require.headers:
            self.include_paths = ""
        self.lib_paths = join_paths(cpp_info.libdirs)
        self.res_paths = join_paths(cpp_info.resdirs)
        self.bin_paths = join_paths(cpp_info.bindirs)
        self.build_paths = join_paths(cpp_info.builddirs)
        self.src_paths = join_paths(cpp_info.srcdirs)
        self.framework_paths = join_paths(cpp_info.frameworkdirs)
        self.libs = join_flags(" ", cpp_info.libs)
        self.system_libs = join_flags(" ", cpp_info.system_libs)
        self.frameworks = join_flags(" ", cpp_info.frameworks)
        self.defines = join_defines(cpp_info.defines, "-D")
        self.compile_definitions = join_defines(cpp_info.defines)
        if require and not require.libs:
            self.lib_paths = ""
            self.libs = ""
            self.system_libs = ""
            self.frameworks = ""

        # For modern CMake targets we need to prepare a list to not
        # loose the elements in the list by replacing " " with ";". Example "-framework Foundation"
        # Issue: #1251
        self.cxxflags_list = join_flags(";", cpp_info.cxxflags)
        self.cflags_list = join_flags(";", cpp_info.cflags)

        # linker flags without magic: trying to mess with - and / =>
        # https://github.com/conan-io/conan/issues/8811
        # frameworks should be declared with cppinfo.frameworks not "-framework Foundation"
        self.sharedlinkflags_list = join_flags(";", cpp_info.sharedlinkflags)
        self.exelinkflags_list = join_flags(";", cpp_info.exelinkflags)

        if require and not require.libs and not require.headers:
            self.defines = ""
            self.compile_definitions = ""
            self.cxxflags_list = ""
            self.cflags_list = ""
            self.sharedlinkflags_list = ""
            self.exelinkflags_list = ""

        build_modules = cpp_info.get_property("cmake_build_modules", "CMakeDeps") or []
        self.build_modules_paths = join_paths(build_modules)
