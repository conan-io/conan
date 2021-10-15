import os
import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conans.errors import ConanException
from conans.util.files import load, save


class XcodeDeps(object):
    _vars_xconfig = textwrap.dedent("""\
        // Definition of Conan variables for {{dep_name}}
        CONAN_{{name}}_ROOT_FOLDER = "{{root_folder}}"
        CONAN_{{name}}_BINARY_DIRECTORIES = "{{bin_dirs}}"
        CONAN_{{name}}_C_COMPILER_FLAGS = "{{c_compiler_flags}}"
        CONAN_{{name}}_CXX_COMPILER_FLAGS = "{{cxx_compiler_flags}}"
        CONAN_{{name}}_LINKER_FLAGS = "{{linker_flags}}"
        CONAN_{{name}}_PREPROCESSOR_DEFINITIONS = "{{definitions}}"
        CONAN_{{name}}_INCLUDE_DIRECTORIES = "{{include_dirs}}"
        CONAN_{{name}}_RESOURCE_DIRECTORIES = "{{res_dirs}}"
        CONAN_{{name}}_LIBRARY_DIRECTORIES = "{{lib_dirs}}"
        CONAN_{{name}}_LIBRARIES = "{{libs}}"
        CONAN_{{name}}_SYSTEM_LIBS = "{{system_libs}}"
        CONAN_{{name}}_FRAMEWORKS_DIRECTORIES = "{{frameworkdirs}}"
        CONAN_{{name}}_FRAMEWORKS = "{{frameworks}}"
        """)

    _conf_xconfig = textwrap.dedent("""\
        {% for dep in deps %}
        // Includes for {{dep}} dependency
        # include "conan_{{dep}}.xcconfig"
        {% endfor %}

        // Include {{dep_name}} vars
        # include "{{vars_filename}}"

        // Compiler options for {{dep_name}}
        HEADER_SEARCH_PATHS = $(inherited) $(CONAN_{{name}}_INCLUDE_DIRECTORIES)
        GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(CONAN_{{name}}_PREPROCESSOR_DEFINITIONS)
        OTHER_CFLAGS = $(inherited) $(CONAN_{{name}}_C_COMPILER_FLAGS)
        OTHER_CPLUSPLUSFLAGS = $(inherited) $(CONAN_{{name}}_CXX_COMPILER_FLAGS)
        FRAMEWORK_SEARCH_PATHS = $(inherited) $(CONAN_{{name}}_FRAMEWORKS_DIRECTORIES)

        // Link options for {{dep_name}}
        LIBRARY_SEARCH_PATHS = $(inherited) $(CONAN_{{name}}_LIBRARY_DIRECTORIES)
        OTHER_LDFLAGS = $(inherited) $(CONAN_{{name}}_LINKER_FLAGS) $(CONAN_{{name}}_LIBRARIES) $(CONAN_{{name}}_SYSTEM_LIBS) $(CONAN_{{name}}_FRAMEWORKS)
        """)

    _dep_xconfig = textwrap.dedent("""\
        // Conan XCodeDeps generated file for {{name}}
        // Includes all configurations for each dependency
        """)

    _all_xconfig = textwrap.dedent("""\
        // Conan XCodeDeps generated file
        // Includes all dependencies
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.build_type
        self.architecture = conanfile.settings.arch
        check_using_build_profile(self._conanfile)

    def generate(self):
        if self.configuration is None:
            raise ConanException("XCodeDeps.configuration is None, it should have a value")
        if self.architecture is None:
            raise ConanException("XCodeDeps.architecture is None, it should have a value")
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _config_filename(self):
        # Default name
        props = [("configuration", self.configuration),
                 ("architecture", self.architecture)]
        name = "".join("_{}".format(v) for _, v in props)
        return name.lower()

    def _vars_xconfig_file(self, dep, name, cpp_info, deps, build=False):
        """
        content for conan_vars_poco_x86_release.xcconfig, containing the variables
        """
        # returns a .xcconfig file with the variables definition for one package for one configuration

        pkg_placeholder = "$(CONAN_{}_ROOT_FOLDER)/".format(name)
        fields = {
            'name': name,
            'root_folder': dep.package_folder,
            'bin_dirs': " ".join('{}'.format(pkg_placeholder + p) for p in cpp_info.bindirs),
            'res_dirs': " ".join('{}'.format(pkg_placeholder + p) for p in cpp_info.resdirs),
            'include_dirs': " ".join('{}'.format(pkg_placeholder + p) for p in cpp_info.includedirs),
            'lib_dirs': " ".join('{}'.format(pkg_placeholder + p) for p in cpp_info.libdirs),
            'libs': " ".join([lib for lib in cpp_info.libs]),
            'system_libs': " ".join([sys_dep for sys_dep in cpp_info.system_libs]),
            'frameworksdirs': " ".join('{}'.format(pkg_placeholder + p) for p in cpp_info.frameworksdirs),
            'frameworks': " ".join(cpp_info.frameworks),
            'definitions': " ".join(cpp_info.defines),
            'c_compiler_flags': " ".join(cpp_info.cflags),
            'cxx_compiler_flags': " ".join(cpp_info.cxxflags),
            'linker_flags': " ".join(cpp_info.sharedlinkflags),
            'exe_flags': " ".join(cpp_info.exelinkflags),
        }
        formatted_template = Template(self._vars_xconfig, trim_blocks=True,
                                      lstrip_blocks=True).render(**fields)
        return formatted_template

    def _conf_xconfig_file(self, dep_name, vars_xconfig_name, deps, build=False):
        """
        content for conan_poco_x86_release.xcconfig, containing the activation
        """
        # TODO: This must include somehow the user/channel, most likely pattern to exclude/include
        template = Template(self._conf_xconfig, trim_blocks=True, lstrip_blocks=True)
        content_multi = template.render(host_context=not build,
                                        name=dep_name,
                                        vars_filename=vars_xconfig_name, deps=deps)
        return content_multi

    def _dep_xconfig_file(self, name, name_general, dep_xconfig_filename):
        # Current directory is the generators_folder
        multi_path = name_general
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._dep_xconfig
            content_multi = Template(content_multi).render({"name": name})

        if dep_xconfig_filename not in content_multi:
            content_multi = content_multi + '\n#include "{}"\n'.format(dep_xconfig_filename)
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _all_xconfig_file(self, name_general, deps):
        """ this is a .xcconfig file including all declared dependencies
        """
        # Current directory is the generators_folder
        multi_path = name_general
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._all_xconfig

        for req, dep in deps.items():
            dep_name = dep.ref.name.replace(".", "_")
            if req.build:
                dep_name += "_build"
            conf_xconfig_name = "conan_{}.xconfig".format(dep_name)
            if conf_xconfig_name in content_multi:
                # already imported
                break
            else:
                content_multi = content_multi + '\n#include "conan_{}.xcconfig"\n'.format(dep_name)
        # To remove all extra blank lines
        content_multi = "\n".join(line for line in content_multi.splitlines() if line.strip())
        return content_multi

    def _content(self):
        result = {}
        general_name = "conandeps.xcconfig"
        conf_name = self._config_filename()

        host_req = list(self._conanfile.dependencies.host.values())
        test_req = list(self._conanfile.dependencies.test.values())

        for dep in host_req + test_req:
            dep_name = dep.ref.name
            dep_name = dep_name.replace(".", "_")
            cpp_info = dep.new_cpp_info.copy()
            cpp_info.aggregate_components()
            public_deps = [d.ref.name.replace(".", "_")
                           for r, d in dep.dependencies.direct_host.items() if r.visible]
            # One file per configuration, with just the variables
            vars_xconfig_name = "conan_{}_vars{}.xcconfig".format(dep_name, conf_name)
            result[vars_xconfig_name] = self._vars_xconfig_file(dep, dep_name, cpp_info, public_deps)
            props_name = "conan_{}{}.xcconfig".format(dep_name, conf_name)
            result[props_name] = self._conf_xconfig_file(dep_name, vars_xconfig_name, public_deps)

            # The entry point for each package, it will have conditionals to the others
            file_dep_name = "conan_{}.xcconfig".format(dep_name)
            dep_content = self._dep_xconfig_file(dep_name, file_dep_name, props_name)
            result[file_dep_name] = dep_content

        build_req = list(self._conanfile.dependencies.build.values())
        for dep in build_req:
            dep_name = dep.ref.name
            dep_name = dep_name.replace(".", "_") + "_build"
            cpp_info = dep.new_cpp_info.copy()
            cpp_info.aggregate_components()
            public_deps = [d.ref.name.replace(".", "_")
                           for r, d in dep.dependencies.direct_host.items() if r.visible]
            # One file per configuration, with just the variables
            vars_xconfig_name = "conan_{}_vars{}.xcconfig".format(dep_name, conf_name)
            result[vars_xconfig_name] = self._vars_xconfig_file(dep, dep_name, cpp_info, public_deps,
                                                                build=True)
            props_name = "conan_{}{}.xcconfig".format(dep_name, conf_name)
            result[props_name] = self._conf_xconfig_file(dep_name, vars_xconfig_name, public_deps,
                                                         build=True)

            # The entry point for each package, it will have conditionals to the others
            file_dep_name = "conan_{}.xcconfig".format(dep_name)
            dep_content = self._dep_xconfig_file(dep_name, file_dep_name, props_name)
            result[file_dep_name] = dep_content

        # Include all direct build_requires for host context. This might change
        direct_deps = self._conanfile.dependencies.filter({"direct": True})
        result[general_name] = self._all_xconfig_file(general_name, direct_deps)

        return result
