import os
import platform
import textwrap

from jinja2 import Template

from conan.internal import check_duplicated_generator
from conan.errors import ConanException
from conans.util.files import save


class BazelDeps(object):

    dependencies_module_template = ""
    dependency_template = textwrap.dedent("""
            load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

            {% for libname, filepath in libs.items() %}
            cc_import(
                name = "{{ libname }}_precompiled",
                {{ library_type }} = "{{ filepath }}",
            )
            {% endfor %}

            {% for libname, (lib_path, dll_path) in shared_with_interface_libs.items() %}
            cc_import(
                name = "{{ libname }}_precompiled",
                interface_library = "{{ lib_path }}",
                shared_library = "{{ dll_path }}",
            )
            {% endfor %}

            filegroup(
                name = "{}_binaries",
                data = glob(["**"]),
                visibility = ["//visibility:public"],
            )

            cc_library(
                name = "{{ name }}",
                {% if headers %}
                hdrs = glob([{{ headers }}]),
                {% endif %}
                {% if includes %}
                includes = [{{ includes }}],
                {% endif %}
                {% if defines %}
                defines = [{{ defines }}],
                {% endif %}
                {% if linkopts %}
                linkopts = [{{ linkopts }}],
                {% endif %}
                visibility = ["//visibility:public"],
                {% if libs or shared_with_interface_libs %}
                deps = [
                    # do not sort
                {% for lib in libs %}
                ":{{ lib }}_precompiled",
                {% endfor %}
                {% for lib in shared_with_interface_libs %}
                ":{{ lib }}_precompiled",
                {% endfor %}
                {% for dep in dependencies %}
                "@{{ dep }}",
                {% endfor %}
                ],
                {% endif %}
            )
        """)


    def __init__(self, conanfile):
        self._conanfile = conanfile

    def _get_bazel_packages(self):
        pass

    def _dependencies_module_content(self):
        context = ""
        content = Template(self.dependencies_module_template).render(context)
        return content

    def _dependency_content(self):
        context = ""
        content = Template(self.dependencies_module_template).render(context)
        return content

    def generate(self):
        check_duplicated_generator(self, self._conanfile)
        for filename, content in self._get_bazel_packages():
            save(filename, content)
