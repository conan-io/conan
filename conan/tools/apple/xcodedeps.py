import os
import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conans.errors import ConanException
from conans.util.files import load, save
from conan.tools.apple.apple import to_apple_arch

GLOBAL_XCCONFIG_TEMPLATE = textwrap.dedent("""\
    // Includes both the toolchain and the dependencies
    // files if they exist

    """)

GLOBAL_XCCONFIG_FILENAME = "conan_config.xcconfig"


def _xcconfig_settings_filename(settings):
    arch = settings.get_safe("arch")
    architecture = to_apple_arch(arch) or arch
    props = [("configuration", settings.get_safe("build_type")),
             ("architecture", architecture),
             ("sdk name", settings.get_safe("os.sdk")),
             ("sdk version", settings.get_safe("os.sdk_version"))]
    name = "".join("_{}".format(v) for _, v in props if v is not None and v)
    name = name.replace(".", "_").replace("-", "_")
    return name.lower()


def _xcconfig_conditional(settings):
    sdk_condition = "*"
    arch = settings.get_safe("arch")
    architecture = to_apple_arch(arch) or arch
    if settings.get_safe("os.sdk"):
        sdk_condition = "{}{}".format(settings.get_safe("os.sdk"), settings.get_safe("os.sdk_version") or "*")

    return "[config={}][arch={}][sdk={}]".format(settings.get_safe("build_type"), architecture, sdk_condition)


def _add_includes_to_file_or_create(filename, template, files_to_include):
    if os.path.isfile(filename):
        content = load(filename)
    else:
        content = template

    for include in files_to_include:
        if include not in content:
            content = content + '#include "{}"\n'.format(include)

    return content


class XcodeDeps(object):
    general_name = "conandeps.xcconfig"

    _vars_xconfig = textwrap.dedent("""\
        // Definition of Conan variables for {{name}}
        CONAN_{{name}}_BINARY_DIRECTORIES{{condition}} = {{bin_dirs}}
        CONAN_{{name}}_C_COMPILER_FLAGS{{condition}} = {{c_compiler_flags}}
        CONAN_{{name}}_CXX_COMPILER_FLAGS{{condition}} = {{cxx_compiler_flags}}
        CONAN_{{name}}_LINKER_FLAGS{{condition}} = {{linker_flags}}
        CONAN_{{name}}_PREPROCESSOR_DEFINITIONS{{condition}} = {{definitions}}
        CONAN_{{name}}_INCLUDE_DIRECTORIES{{condition}} = {{include_dirs}}
        CONAN_{{name}}_RESOURCE_DIRECTORIES{{condition}} = {{res_dirs}}
        CONAN_{{name}}_LIBRARY_DIRECTORIES{{condition}} = {{lib_dirs}}
        CONAN_{{name}}_LIBRARIES{{condition}} = {{libs}}
        CONAN_{{name}}_SYSTEM_LIBS{{condition}} = {{system_libs}}
        CONAN_{{name}}_FRAMEWORKS_DIRECTORIES{{condition}} = {{frameworkdirs}}
        CONAN_{{name}}_FRAMEWORKS{{condition}} = {{frameworks}}
        """)

    _conf_xconfig = textwrap.dedent("""\
        // Include {{name}} vars
        #include "{{vars_filename}}"

        // Compiler options for {{name}}
        HEADER_SEARCH_PATHS_{{name}} = $(CONAN_{{name}}_INCLUDE_DIRECTORIES)
        GCC_PREPROCESSOR_DEFINITIONS_{{name}} = $(CONAN_{{name}}_PREPROCESSOR_DEFINITIONS)
        OTHER_CFLAGS_{{name}} = $(CONAN_{{name}}_C_COMPILER_FLAGS)
        OTHER_CPLUSPLUSFLAGS_{{name}} = $(CONAN_{{name}}_CXX_COMPILER_FLAGS)
        FRAMEWORK_SEARCH_PATHS_{{name}} = $(CONAN_{{name}}_FRAMEWORKS_DIRECTORIES)

        // Link options for {{name}}
        LIBRARY_SEARCH_PATHS_{{name}} = $(CONAN_{{name}}_LIBRARY_DIRECTORIES)
        OTHER_LDFLAGS_{{name}} = $(CONAN_{{name}}_LINKER_FLAGS) $(CONAN_{{name}}_LIBRARIES) $(CONAN_{{name}}_SYSTEM_LIBS) $(CONAN_{{name}}_FRAMEWORKS)
        """)

    _dep_xconfig = textwrap.dedent("""\
        // Conan XcodeDeps generated file for {{name}}
        // Includes all configurations for each dependency
        {% for dep in deps -%}
        // Includes for {{dep}} dependency
        #include "conan_{{dep}}.xcconfig"
        {%- endfor %}
        #include "{{dep_xconfig_filename}}"

        HEADER_SEARCH_PATHS = $(inherited) $(HEADER_SEARCH_PATHS_{{name}})
        GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{{name}})
        OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{{name}})
        OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{{name}})
        FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{{name}})

        // Link options for {{name}}
        LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{{name}})
        OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{{name}})
         """)

    _all_xconfig = textwrap.dedent("""\
        // Conan XcodeDeps generated file
        // Includes all direct dependencies
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.get_safe("build_type")
        arch = conanfile.settings.get_safe("arch")
        self.architecture = to_apple_arch(arch) or arch
        self.os_version = conanfile.settings.get_safe("os.version")
        self.sdk = conanfile.settings.get_safe("os.sdk")
        self.sdk_version = conanfile.settings.get_safe("os.sdk_version")
        check_using_build_profile(self._conanfile)

    def generate(self):
        if self.configuration is None:
            raise ConanException("XcodeDeps.configuration is None, it should have a value")
        if self.architecture is None:
            raise ConanException("XcodeDeps.architecture is None, it should have a value")
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _vars_xconfig_file(self, dep, name, cpp_info):
        """
        returns a .xcconfig file with the variables definition for one package for one configuration
        """

        fields = {
            'name': name,
            'bin_dirs': " ".join('"{}"'.format(p) for p in cpp_info.bindirs),
            'res_dirs': " ".join('"{}"'.format(p) for p in cpp_info.resdirs),
            'include_dirs': " ".join('"{}"'.format(p) for p in cpp_info.includedirs),
            'lib_dirs': " ".join('"{}"'.format(p) for p in cpp_info.libdirs),
            'libs': " ".join("-l{}".format(lib) for lib in cpp_info.libs),
            'system_libs': " ".join("-l{}".format(sys_lib) for sys_lib in cpp_info.system_libs),
            'frameworksdirs': " ".join('"{}"'.format(p) for p in cpp_info.frameworkdirs),
            'frameworks': " ".join("-framework {}".format(framework) for framework in cpp_info.frameworks),
            'definitions': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in cpp_info.defines),
            'c_compiler_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in cpp_info.cflags),
            'cxx_compiler_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in cpp_info.cxxflags),
            'linker_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in cpp_info.sharedlinkflags),
            'exe_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in cpp_info.exelinkflags),
            'condition': _xcconfig_conditional(self._conanfile.settings)
        }
        formatted_template = Template(self._vars_xconfig).render(**fields)
        return formatted_template

    def _conf_xconfig_file(self, dep_name, vars_xconfig_name):
        """
        content for conan_poco_x86_release.xcconfig, containing the activation
        """
        template = Template(self._conf_xconfig)
        content_multi = template.render(name=dep_name, vars_filename=vars_xconfig_name)
        return content_multi

    def _dep_xconfig_file(self, name, name_general, dep_xconfig_filename, deps):
        # Current directory is the generators_folder
        multi_path = name_general
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._dep_xconfig
            content_multi = Template(content_multi).render({"name": name,
                                                            "dep_xconfig_filename": dep_xconfig_filename,
                                                            "deps": deps})

        if dep_xconfig_filename not in content_multi:
            content_multi = content_multi.replace('.xcconfig"',
                                                  '.xcconfig"\n#include "{}"'.format(dep_xconfig_filename),
                                                  1)

        return content_multi

    def _all_xconfig_file(self, deps):
        """
        this is a .xcconfig file including all declared dependencies
        """
        content_multi = self._all_xconfig

        for req, dep in deps.items():
            dep_name = dep.ref.name.replace(".", "_").replace("-", "_")
            content_multi = content_multi + '\n#include "conan_{}.xcconfig"\n'.format(dep_name)
        return content_multi

    @property
    def _global_xconfig_content(self):
        return _add_includes_to_file_or_create(GLOBAL_XCCONFIG_FILENAME,
                                               GLOBAL_XCCONFIG_TEMPLATE,
                                               [self.general_name])

    def _content(self):
        result = {}
        conf_name = _xcconfig_settings_filename(self._conanfile.settings)

        for dep in self._conanfile.dependencies.host.values():
            dep_name = dep.ref.name
            dep_name = dep_name.replace(".", "_").replace("-", "_")
            cpp_info = dep.cpp_info.aggregated_components()
            public_deps = [d.ref.name.replace(".", "_").replace("-", "_")
                           for r, d in dep.dependencies.direct_host.items() if r.visible]

            # One file per configuration, with just the variables
            vars_xconfig_name = "conan_{}_vars{}.xcconfig".format(dep_name, conf_name)
            result[vars_xconfig_name] = self._vars_xconfig_file(dep, dep_name, cpp_info)
            props_name = "conan_{}{}.xcconfig".format(dep_name, conf_name)
            result[props_name] = self._conf_xconfig_file(dep_name, vars_xconfig_name)

            # The entry point for each package
            file_dep_name = "conan_{}.xcconfig".format(dep_name)
            dep_content = self._dep_xconfig_file(dep_name, file_dep_name, props_name, public_deps)
            result[file_dep_name] = dep_content

        # Include all direct build_requires for host context.
        direct_deps = self._conanfile.dependencies.filter({"direct": True, "build": False})
        result[self.general_name] = self._all_xconfig_file(direct_deps)

        result[GLOBAL_XCCONFIG_FILENAME] = self._global_xconfig_content

        return result
