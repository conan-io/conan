import os
import jinja2
from jinja2 import Template
import textwrap

from conans.errors import ConanException
from conans.model import dependencies
from conans.model.conanfile_interface import ConanFileInterface


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

    @property
    def build_modules_activated(self):
        if self.conanfile.is_build_context:
            return self.conanfile.ref.name in self.qbsdeps.build_context_build_modules
        else:
            return self.conanfile.ref.name not in self.qbsdeps.build_context_build_modules

    def render(self):
        print("### QbsModuleTemplate.render")
        context = self.context
        print("#### context: {}".format(context))
        if context is None:
            return
        return Template(self.template, trim_blocks=True, lstrip_blocks=True,
                        undefined=jinja2.StrictUndefined).render(context)

    @property
    def context(self):
        print("### QbsModuleTemplate.context")
        pkg_version = self.conanfile.ref.version
        cpp = DepsCppQbs(
            self.conanfile.cpp_info.components[self.component_name], self.conanfile.package_folder)
        dependencies = self.get_direct_dependencies()

        print("#### pkg_version: {}".format(pkg_version))
        # print("#### cpp: {}".format(cpp))
        print("#### dependencies: {}".format(dependencies))

        return {
            "pkg_version": pkg_version,
            "cpp": cpp,
            "dependencies": dependencies
        }

    def get_direct_dependencies(self):
        print("### QbsModuleTemplate.get_direct_dependencies")
        ret = {}

        def create_module(conanfile, comp, comp_name):
            return {"{}.{}".format(self.get_module_name(conanfile),
                                   self.get_component_name(comp, comp_name)):
                    self.conanfile.ref.version}

        cpp_info = self.conanfile.cpp_info.components[self.component_name]
        for req in cpp_info.requires:
            pkg_name, comp_name = req.split("::") if "::" in req else (
                self.conanfile.ref.name, req)
            if "::" not in req:
                ret.update(create_module(self.conanfile, cpp_info, comp_name))
            else:
                print("#### **** {} | {} {}".format(req, pkg_name, comp_name))
                req_conanfile = self.conanfile.dependencies.direct_host[pkg_name]
                if req_conanfile.cpp_info.has_components:
                    print("#### append module {}.{}".format(pkg_name, comp_name))
                    ret.update(create_module(req_conanfile, req_conanfile.cpp_info, comp_name))
                else:
                    print("#### append module {}".format(pkg_name))
                    ret[self.get_module_name(req_conanfile)] = req_conanfile.ref.version

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
        ret = self.get_module_name(self.conanfile) + self.suffix
        if self.conanfile.cpp_info.has_components:
            assert(self.component_name)
            ret = "{}/{}".format(ret, self.component_name)
        return ret

    def get_module_name(self, dependency):
        print("### get qbs_module_name from {}".format(dependency))
        return dependency.cpp_info.get_property("qbs_module_name", "QbsDeps") or \
            dependency.ref.name

    def get_component_name(self, component, default):
        print("### get qbs_module_name from {}, default {}".format(component, default))
        return component.get_property("qbs_module_name", "QbsDeps") or \
            default


class DepsCppQbs(object):
    def __init__(self, cpp_info, package_folder):
        def prepent_package_folder(paths):
            print("################# Yolo")
            print("################# {}".format(package_folder))
            return [os.path.join(package_folder, path) for path in paths]

        self.includedirs = prepent_package_folder(cpp_info.includedirs)
        self.libdirs = prepent_package_folder(cpp_info.libdirs)
        self.system_libs = cpp_info.system_libs
        self.libs = cpp_info.libs
        self.frameworkdirs = prepent_package_folder(cpp_info.frameworkdirs)
        self.frameworks = cpp_info.frameworks
        self.defines = cpp_info.defines
        self.cflags = cpp_info.cflags
        self.cxxflags = cpp_info.cxxflags
        self.sharedlinkflags = cpp_info.sharedlinkflags
        self.exelinkflags = cpp_info.exelinkflags
