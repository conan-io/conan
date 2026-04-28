import os
import re
import textwrap
from jinja2 import Template

from conan.internal import check_duplicated_generator
from conan.errors import ConanException
from conan.internal.util.files import load, save
from conan.tools.apple.apple import _to_apple_arch

GLOBAL_XCCONFIG_TEMPLATE = textwrap.dedent("""\
    // Includes both the toolchain and the dependencies
    // files if they exist

    """)

GLOBAL_XCCONFIG_FILENAME = "conan_config.xcconfig"


def _format_name(name):
    return re.sub(r'[^A-Za-z0-9_]', '_', name).lower()


def _xcconfig_settings_filename(settings, configuration):
    arch = settings.get_safe("arch")
    architecture = _to_apple_arch(arch) or arch
    props = [("configuration", configuration),
             ("architecture", architecture),
             ("sdk name", settings.get_safe("os.sdk")),
             ("sdk version", settings.get_safe("os.sdk_version"))]
    name = "".join("_{}".format(v) for _, v in props if v is not None and v)
    return _format_name(name)


def _xcconfig_conditional(settings, configuration):
    sdk_condition = "*"
    arch = settings.get_safe("arch")
    architecture = _to_apple_arch(arch) or arch
    sdk = settings.get_safe("os.sdk") if settings.get_safe("os") != "Macos" else "macosx"
    if sdk:
        sdk_condition = "{}{}".format(sdk, settings.get_safe("os.sdk_version") or "*")

    return "[config={}][arch={}][sdk={}]".format(configuration, architecture, sdk_condition)


def _add_includes_to_file_or_create(filename, template, files_to_include):
    if os.path.isfile(filename):
        content = load(filename)
    else:
        content = template

    for include in files_to_include:
        if include not in content:
            content = content + '#include "{}"\n'.format(include)

    return content


class XcodeDeps:
    general_name = "conandeps.xcconfig"

    _conf_xconfig = textwrap.dedent("""\
        PACKAGE_ROOT_{{pkg_name}}{{condition}} = {{root}}
        // Compiler options for {{pkg_name}}::{{comp_name}}
        SYSTEM_HEADER_SEARCH_PATHS_{{pkg_name}}_{{comp_name}}{{condition}} = {{include_dirs}}
        GCC_PREPROCESSOR_DEFINITIONS_{{pkg_name}}_{{comp_name}}{{condition}} = {{definitions}}
        OTHER_CFLAGS_{{pkg_name}}_{{comp_name}}{{condition}} = {{c_compiler_flags}}
        OTHER_CPLUSPLUSFLAGS_{{pkg_name}}_{{comp_name}}{{condition}} = {{cxx_compiler_flags}}
        FRAMEWORK_SEARCH_PATHS_{{pkg_name}}_{{comp_name}}{{condition}} = {{frameworkdirs}}

        // Link options for {{pkg_name}}::{{comp_name}}
        LIBRARY_SEARCH_PATHS_{{pkg_name}}_{{comp_name}}{{condition}} = {{lib_dirs}}
        OTHER_LDFLAGS_{{pkg_name}}_{{comp_name}}{{condition}} = {{linker_flags}} {{libs}} {{system_libs}} {{frameworks}}
        """)

    _dep_xconfig = textwrap.dedent("""\
        // Conan XcodeDeps generated file for {{pkg_name}}::{{comp_name}}
        // Includes all configurations for each dependency
        {% for include in deps_includes %}
        #include "{{include}}"
        {% endfor %}
        #include "{{dep_xconfig_filename}}"

        SYSTEM_HEADER_SEARCH_PATHS = $(inherited) $(SYSTEM_HEADER_SEARCH_PATHS_{{pkg_name}}_{{comp_name}})
        GCC_PREPROCESSOR_DEFINITIONS = $(inherited) $(GCC_PREPROCESSOR_DEFINITIONS_{{pkg_name}}_{{comp_name}})
        OTHER_CFLAGS = $(inherited) $(OTHER_CFLAGS_{{pkg_name}}_{{comp_name}})
        OTHER_CPLUSPLUSFLAGS = $(inherited) $(OTHER_CPLUSPLUSFLAGS_{{pkg_name}}_{{comp_name}})
        FRAMEWORK_SEARCH_PATHS = $(inherited) $(FRAMEWORK_SEARCH_PATHS_{{pkg_name}}_{{comp_name}})

        // Link options for {{pkg_name}}_{{comp_name}}
        LIBRARY_SEARCH_PATHS = $(inherited) $(LIBRARY_SEARCH_PATHS_{{pkg_name}}_{{comp_name}})
        OTHER_LDFLAGS = $(inherited) $(OTHER_LDFLAGS_{{pkg_name}}_{{comp_name}})
        """)

    _all_xconfig = textwrap.dedent("""\
        // Conan XcodeDeps generated file
        // Includes all direct dependencies
        """)

    _pkg_xconfig = textwrap.dedent("""\
        // Conan XcodeDeps generated file
        // Includes all components for the package
        """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        self.configuration = conanfile.settings.get_safe("build_type")
        arch = conanfile.settings.get_safe("arch")
        self.architecture = _to_apple_arch(arch, default=arch)
        self.os_version = conanfile.settings.get_safe("os.version")
        self.sdk = conanfile.settings.get_safe("os.sdk")
        self.sdk_version = conanfile.settings.get_safe("os.sdk_version")

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        if self.configuration is None:
            raise ConanException("XcodeDeps.configuration is None, it should have a value")
        if self.architecture is None:
            raise ConanException("XcodeDeps.architecture is None, it should have a value")
        generator_files = self._content()
        for generator_file, content in generator_files.items():
            save(generator_file, content)

    def _conf_xconfig_file(self, require, pkg_name, comp_name, package_folder, transitive_cpp_infos):
        """
        content for conan_poco_x86_release.xcconfig, containing the activation
        """
        def _merged_vars(name):
            merged = [var for cpp_info in transitive_cpp_infos for var in getattr(cpp_info, name)]
            return list(dict.fromkeys(merged).keys())

        # TODO: Investigate if paths can be made relative to "root" folder
        fields = {
            'pkg_name': pkg_name,
            'comp_name': comp_name,
            'root': package_folder,
            'include_dirs': " ".join('"{}"'.format(p) for p in _merged_vars("includedirs")),
            'lib_dirs': " ".join('"{}"'.format(p) for p in _merged_vars("libdirs")),
            'libs': " ".join("-l{}".format(lib) for lib in _merged_vars("libs")),
            'system_libs': " ".join("-l{}".format(sys_lib) for sys_lib in _merged_vars("system_libs")),
            'frameworkdirs': " ".join('"{}"'.format(p) for p in _merged_vars("frameworkdirs")),
            'frameworks': " ".join("-framework {}".format(framework) for framework in _merged_vars("frameworks")),
            'definitions': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in _merged_vars("defines")),
            'c_compiler_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in _merged_vars("cflags")),
            'cxx_compiler_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in _merged_vars("cxxflags")),
            'linker_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in _merged_vars("sharedlinkflags")),
            'exe_flags': " ".join('"{}"'.format(p.replace('"', '\\"')) for p in _merged_vars("exelinkflags")),
            'condition': _xcconfig_conditional(self._conanfile.settings, self.configuration)
        }

        if not require.headers:
            fields["include_dirs"] = ""

        if not require.libs:
            fields["lib_dirs"] = ""
            fields["libs"] = ""
            fields["system_libs"] = ""
            fields["frameworkdirs"] = ""
            fields["frameworks"] = ""

        if not require.libs and not require.headers:
            fields["definitions"] = ""
            fields["c_compiler_flags"] = ""
            fields["cxx_compiler_flags"] = ""
            fields["linker_flags"] = ""
            fields["exe_flags"] = ""

        template = Template(self._conf_xconfig)
        content_multi = template.render(**fields)
        return content_multi

    def _dep_xconfig_file(self, pkg_name, comp_name, name_general, dep_xconfig_filename, reqs):
        # Current directory is the generators_folder
        multi_path = name_general
        if os.path.isfile(multi_path):
            content_multi = load(multi_path)
        else:
            content_multi = self._dep_xconfig

            def _get_includes(components):
                # if we require the root component dep::dep include conan_dep.xcconfig
                # for components (dep::component) include conan_dep_component.xcconfig
                return [f"conan_{_format_name(component[0])}.xcconfig" if component[0] == component[1]
                        else f"conan_{_format_name(component[0])}_{_format_name(component[1])}.xcconfig"
                        for component in components]

            content_multi = Template(content_multi).render({"pkg_name": pkg_name,
                                                            "comp_name": comp_name,
                                                            "dep_xconfig_filename": dep_xconfig_filename,
                                                            "deps_includes": _get_includes(reqs)})

        if dep_xconfig_filename not in content_multi:
            content_multi = content_multi.replace('.xcconfig"',
                                                  '.xcconfig"\n#include "{}"'.format(dep_xconfig_filename),
                                                  1)

        return content_multi

    def _all_xconfig_file(self, deps, content):
        """
        this is a .xcconfig file including all declared dependencies
        """
        content_multi = content or self._all_xconfig

        for dep in deps.values():
            include_file = f'conan_{_format_name(dep.ref.name)}.xcconfig'
            if include_file not in content_multi:
                content_multi = content_multi + f'\n#include "{include_file}"\n'
        return content_multi

    def _pkg_xconfig_file(self, components):
        """
        this is a .xcconfig file including the components for each package
        """
        content_multi = self._pkg_xconfig
        for pkg_name, comp_name in components:
            content_multi = content_multi + '\n#include "conan_{}_{}.xcconfig"\n'.format(pkg_name,
                                                                                         comp_name)
        return content_multi

    @property
    def _global_xconfig_content(self):
        return _add_includes_to_file_or_create(GLOBAL_XCCONFIG_FILENAME,
                                               GLOBAL_XCCONFIG_TEMPLATE,
                                               [self.general_name])

    def _get_content_for_component(self, require, pkg_name, component_name, package_folder, transitive_cpp_infos):
        result = {}

        conf_name = _xcconfig_settings_filename(self._conanfile.settings, self.configuration)

        props_name = "conan_{}_{}{}.xcconfig".format(pkg_name, component_name, conf_name)
        result[props_name] = self._conf_xconfig_file(require, pkg_name, component_name, package_folder, transitive_cpp_infos)

        # The entry point for each package
        file_dep_name = "conan_{}_{}.xcconfig".format(pkg_name, component_name)
        dep_content = self._dep_xconfig_file(pkg_name, component_name, file_dep_name, props_name, [])

        result[file_dep_name] = dep_content
        return result

    @staticmethod
    def _collect_all_transitive(cpp_info, pkg_dep, all_deps, collected, visited=None):
        """Recursively collect all transitive CppInfo objects (internal and external)
        into a flat list.

        :param cpp_info: current CppInfo being processed (root or component)
        :param pkg_dep: dependency object owning the cpp_info
        :param all_deps: dict {ref.name: dep} of all available host/test deps
        :param collected: output list accumulating the CppInfo objects
        :param visited: set of id(cpp_info) already processed (created automatically)
        """
        if visited is None:
            visited = set()

        key = id(cpp_info)
        if key in visited:
            return
        visited.add(key)
        collected.append(cpp_info)

        if cpp_info.requires:
            for req in cpp_info.requires:
                if "::" not in req:
                    # Internal component from the same package
                    XcodeDeps._collect_all_transitive(
                        pkg_dep.cpp_info.components.get(req), pkg_dep,
                        all_deps, collected, visited)
                else:
                    XcodeDeps._resolve_external(req, all_deps, collected, visited)
        elif not pkg_dep.cpp_info.has_components:
            for _, d in pkg_dep.dependencies.direct_host.items():
                XcodeDeps._resolve_external(f"{d.ref.name}::{d.ref.name}",
                                           all_deps, collected, visited)

    @staticmethod
    def _resolve_external(req, all_deps, collected, visited):
        """Resolve and follow an external requirement (pkg::comp)."""

        ext_pkg, ext_comp = req.split("::", 1)
        ext_dep = all_deps.get(ext_pkg)
        if ext_dep is None:  # skipped or not visible dependency
            return

        if not ext_dep.cpp_info.has_components:
            # Package without components: use root cpp_info directly
            XcodeDeps._collect_all_transitive(ext_dep.cpp_info, ext_dep, all_deps,
                                              collected, visited)
        elif ext_pkg == ext_comp:
            # Dependency on the whole package (pkg::pkg): collect all its components
            for comp in ext_dep.cpp_info.get_sorted_components().values():
                XcodeDeps._collect_all_transitive(comp, ext_dep, all_deps,
                                                  collected, visited)
        else:
            # Dependency on a specific component (pkg::comp)
            XcodeDeps._collect_all_transitive(
                ext_dep.cpp_info.components.get(ext_comp), ext_dep,
                all_deps, collected, visited)

    def _content(self):
        result = {}

        # Generate the config files for each component with name conan_pkgname_compname.xcconfig
        # If a package has no components the name is conan_pkgname_pkgname.xcconfig
        # All components are included in the conan_pkgname.xcconfig file
        host_req = self._conanfile.dependencies.host
        test_req = self._conanfile.dependencies.test
        all_deps = {dep.ref.name: dep
                    for _, dep in list(host_req.items()) + list(test_req.items())}

        direct_deps = self._conanfile.dependencies.filter({"direct": True,
                                                           "build": False,
                                                           "skip": False})
        for require, dep in direct_deps.items():

            dep_name = _format_name(dep.ref.name)

            include_components_names = []
            if dep.cpp_info.has_components:

                sorted_components = dep.cpp_info.get_sorted_components().items()
                for comp_name, comp_cpp_info in sorted_components:
                    comp_name = _format_name(comp_name)

                    transitive_cpp_infos = []
                    self._collect_all_transitive(comp_cpp_info, dep, all_deps,
                                                 transitive_cpp_infos)

                    # In case dep is editable and package_folder=None
                    pkg_folder = dep.package_folder or dep.recipe_folder
                    component_content = self._get_content_for_component(require, dep_name, comp_name,
                                                                        pkg_folder,
                                                                        transitive_cpp_infos)
                    include_components_names.append((dep_name, comp_name))
                    result.update(component_content)
            else:
                transitive_cpp_infos = []
                self._collect_all_transitive(dep.cpp_info, dep, all_deps,
                                             transitive_cpp_infos)
                # In case dep is editable and package_folder=None
                pkg_folder = dep.package_folder or dep.recipe_folder
                root_content = self._get_content_for_component(require, dep_name, dep_name, pkg_folder,
                                                               transitive_cpp_infos)
                include_components_names.append((dep_name, dep_name))
                result.update(root_content)

            result["conan_{}.xcconfig".format(dep_name)] = self._pkg_xconfig_file(include_components_names)

        all_file_content = ""

        # Include direct requires
        direct_deps = self._conanfile.dependencies.filter({"direct": True, "build": False, "skip": False})
        result[self.general_name] = self._all_xconfig_file(direct_deps, all_file_content)

        result[GLOBAL_XCCONFIG_FILENAME] = self._global_xconfig_content

        return result
