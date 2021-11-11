import jinja2
from jinja2 import Template
import textwrap

import conan.tools.qbs.utils as utils


class QbsModuleTemplate(object):
    def __init__(self, qbsdeps, require, conanfile, component):
        self.qbsdeps = qbsdeps
        self.require = require
        self.conanfile = conanfile
        self.component_name = component

    @property
    def suffix(self):
        if not self.conanfile.is_build_context:
            return ""
        return self.qbsdeps.build_context_suffix.get(self.conanfile.ref.name, "")

    def render(self):
        context = self.context
        if context is None:
            return
        return Template(self.template, trim_blocks=True, lstrip_blocks=True,
                        undefined=jinja2.StrictUndefined).render(context)

    @property
    def context(self):
        pkg_version = self.conanfile.ref.version
        cpp = DepsCppQbs(
            self.conanfile.cpp_info.components[self.component_name], self.conanfile.package_folder)
        dependencies = self.get_direct_dependencies()

        return {
            "pkg_version": pkg_version,
            "cpp": cpp,
            "dependencies": dependencies
        }

    def get_direct_dependencies(self):
        ret = {}

        def create_module(conanfile, comp, comp_name):
            return {"{}.{}".format(utils.get_module_name(conanfile),
                                   utils.get_component_name(comp, comp_name)):
                    conanfile.ref.version}

        cpp_info = self.conanfile.cpp_info.components[self.component_name]
        for req in cpp_info.requires:
            pkg_name, comp_name = req.split("::") if "::" in req else (
                self.conanfile.ref.name, req)
            if "::" not in req:
                ret.update(create_module(self.conanfile, cpp_info, comp_name))
            else:
                req_conanfile = self.conanfile.dependencies.direct_host[pkg_name]
                if req_conanfile.cpp_info.has_components:
                    ret.update(create_module(req_conanfile, req_conanfile.cpp_info, comp_name))
                else:
                    ret[utils.get_module_name(req_conanfile)] = req_conanfile.ref.version

        return ret

    @ property
    def template(self):
        ret = textwrap.dedent("""\
                Module {
                    version: "{{ pkg_version }}"
                    cpp.includePaths: [
                        {% for include_path in cpp.includedirs %}
                        "{{ include_path }}",
                        {% endfor %}
                    ]
                    cpp.libraryPaths: [
                        {% for library_path in cpp.libdirs %}
                        "{{ library_path }}",
                        {% endfor %}
                    ]
                    cpp.dynamicLibraries: [
                        {% for library in cpp.system_libs %}
                        "{{ library }}",
                        {% endfor %}
                        {% for library in cpp.libs %}
                        "{{ library }}",
                        {% endfor %}
                    ]
                    cpp.frameworkPaths: [
                        {% for framework_path in cpp.frameworkdirs %}
                        "{{ framework_path }}",
                        {% endfor %}
                    ]
                    cpp.frameworks: [
                        {% for framework in cpp.frameworks %}
                        "{{ framework }}",
                        {% endfor %}
                    ]
                    cpp.defines: [
                        {% for define in cpp.defines %}
                        '{{ define }}',
                        {% endfor %}
                    ]
                    cpp.cFlags: [
                        {% for c_flag in cpp.cflags %}
                        "{{ c_flag }}",
                        {% endfor %}
                    ]
                    cpp.cxxFlags: [
                        {% for cxx_flag in cpp.cxxflags %}
                        "{{ cxx_flag }}",
                        {% endfor %}
                    ]
                    cpp.linkerFlags: [
                        {% for linker_flag in cpp.sharedlinkflags %}
                        "{{ linker_flag }}",
                        {% endfor %}
                        {% for linker_flag in cpp.exelinkflags %}
                        "{{ linker_flag }}",
                        {% endfor %}
                    ]
                    Depends { name: "cpp" }
                    {% for name, version in dependencies.items() %}
                    Depends { name: "{{ name }}"; version: "{{ version }}" }
                    {% endfor %}
                }
            """)
        return ret

    @ property
    def filename(self):
        ret = utils.get_module_name(self.conanfile) + self.suffix
        if self.conanfile.cpp_info.has_components:
            assert(self.component_name)
            ret = "{}/{}".format(ret, self.component_name)
        return ret


class DepsCppQbs(object):
    def __init__(self, cpp_info, package_folder):
        def prepend_package_folder(paths):
            return utils.prepend_package_folder(paths, package_folder)

        self.includedirs = prepend_package_folder(cpp_info.includedirs)
        self.libdirs = prepend_package_folder(cpp_info.libdirs)
        self.system_libs = cpp_info.system_libs
        self.libs = cpp_info.libs
        self.frameworkdirs = prepend_package_folder(cpp_info.frameworkdirs)
        self.frameworks = cpp_info.frameworks
        self.defines = cpp_info.defines
        self.cflags = cpp_info.cflags
        self.cxxflags = cpp_info.cxxflags
        self.sharedlinkflags = cpp_info.sharedlinkflags
        self.exelinkflags = cpp_info.exelinkflags

    def __eq__(self, other):
        return self.includedirs == other.includedirs and \
            self.libdirs == other.libdirs and \
            self.system_libs == other.system_libs and \
            self.libs == other.libs and \
            self.frameworkdirs == other.frameworkdirs and \
            self.frameworks == other.frameworks and \
            self.defines == other.defines and \
            self.cflags == other.cflags and \
            self.cxxflags == other.cxxflags and \
            self.sharedlinkflags == other.sharedlinkflags and \
            self.exelinkflags == other.exelinkflags
