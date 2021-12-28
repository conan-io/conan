import os
import platform
import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conans.util.files import save


class BazelDeps(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile
        check_using_build_profile(self._conanfile)

    def generate(self):
        local_repositories = []

        for build_dependency in self._conanfile.dependencies.direct_build.values():
            content = self._get_build_dependency_buildfile_content(build_dependency)
            filename = self._save_dependendy_buildfile(build_dependency, content)

            local_repository = self._create_new_local_repository(build_dependency, filename)
            local_repositories.append(local_repository)

        for dependency in self._conanfile.dependencies.host.values():
            content = self._get_dependency_buildfile_content(dependency)
            filename = self._save_dependendy_buildfile(dependency, content)

            local_repository = self._create_new_local_repository(dependency, filename)
            local_repositories.append(local_repository)

        content = self._get_main_buildfile_content(local_repositories)
        self._save_main_buildfiles(content)

    def _save_dependendy_buildfile(self, dependency, buildfile_content):
        filename = '{}/conandeps/{}/BUILD'.format(
            self._conanfile.install_folder, dependency.ref.name)
        filename = filename.replace(os.sep, '/')
        save(filename, buildfile_content)
        return filename

    def _get_build_dependency_buildfile_content(self, dependency):
        filegroup = textwrap.dedent("""
            filegroup(
                name = "{}_binaries",
                data = glob(["**"]),
                visibility = ["//visibility:public"],
            )
        """).format(dependency.ref.name)

        return filegroup

    def _get_dependency_buildfile_content(self, dependency):
        template = textwrap.dedent("""
            load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

            {% for lib in libs %}
            cc_import(
                name = "{{ lib }}_precompiled",
                static_library = "{{ libdir }}/{{ lib }}"
            )
            {% endfor %}

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
                {% if libs %}
                deps = [
                {% for lib in libs %}
                ":{{ lib }}_precompiled",
                {% endfor %}
                ],
                {% endif %}
            )

        """)

        system = platform.system()
        if not system:
            system == 'Linux'

        cpp_info = dependency.cpp_info.aggregated_components()

        if not cpp_info.libs and not cpp_info.includedirs:
            return None

        headers = []
        includes = []

        for path in cpp_info.includedirs:
            path = path.replace(os.sep, '/')
            headers.append('"{}/**"'.format(path))
            includes.append('"{}"'.format(path))

        headers = ', '.join(headers)
        includes = ', '.join(includes)

        defines = ('"{}"'.format(define.replace('"', "'"))
                   for define in cpp_info.defines)
        defines = ', '.join(defines)

        linkopts = []
        for system_lib in cpp_info.system_libs:
            if system == "Windows":
                linkopts.append('"/DEFAULTLIB:{}"'.format(system_lib))
            else:
                linkopts.append('"-l{}"'.format(system_lib))
        linkopts = ', '.join(linkopts)

        libs = []
        for libname in cpp_info.libs:
            if system == "Windows":
                libs.append("{}.lib".format(libname))
            else:
                libs.append("lib{}.a".format(libname))

        context = {
            "name": dependency.ref.name,
            "libs": libs,
            "libdir": cpp_info.libdirs[0].replace(os.sep, '/'),
            "headers": headers,
            "includes": includes,
            "defines": defines,
            "linkopts": linkopts
        }

        content = Template(template).render(**context)
        return content

    def _create_new_local_repository(self, dependency, dependency_buildfile_name):
        package_folder = dependency.package_folder.replace(os.sep, '/')
        snippet = textwrap.dedent("""
            native.new_local_repository(
                name="{}",
                path="{}",
                build_file="{}",
            )
        """).format(
            dependency.ref.name,
            package_folder,
            dependency_buildfile_name
        )

        return snippet

    def _get_main_buildfile_content(self, local_repositories):
        template = textwrap.dedent("""
            def load_conan_dependencies():
                {}
        """)

        if local_repositories:
            function_content = "\n".join(local_repositories)
            function_content = '    '.join(line for line in function_content.splitlines(True))
        else:
            function_content = '    pass'

        content = template.format(function_content)

        return content

    def _save_main_buildfiles(self, content):
        # A BUILD file must exist, even if it's empty, in order for bazel
        # to detect it as a bazel package and allow to load the .bzl files
        save("conandeps/BUILD", "")

        save("conandeps/dependencies.bzl", content)
