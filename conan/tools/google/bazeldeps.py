import textwrap

from jinja2 import Template

from conans.util.files import save


class BazelDeps(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self):
        local_repositories = []
        for dependency in self._conanfile.dependencies.transitive_host_requires:
            filename = self._create_bazel_buildfile(dependency)
            local_repositories.append(self._create_new_local_repository(dependency, filename))

        self._save_dependencies_file(local_repositories)

    def _create_bazel_buildfile(self, dependency):
        template = textwrap.dedent("""
            load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

            {% for lib in libs %}
            cc_import(
                name = "{{ lib }}_precompiled",
                static_library = "{{ libdir }}/lib{{ lib }}.a"
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
                visibility = ["//visibility:public"]
            )

        """)

        dependency.new_cpp_info.aggregate_components()

        if not dependency.new_cpp_info.libs and not dependency.new_cpp_info.includedirs:
            return None

        headers = []
        includes = []

        for path in dependency.new_cpp_info.includedirs:
            headers.append('"{}/**"'.format(path))
            includes.append('"{}"'.format(path))

        headers = ', '.join(headers)
        includes = ', '.join(includes)

        defines = ('"{}"'.format(define) for define in dependency.new_cpp_info.defines)
        defines = ', '.join(defines)

        context = {
            "name": dependency.ref.name,
            "libs": dependency.new_cpp_info.libs,
            "libdir": dependency.new_cpp_info.libdirs[0],
            "headers": headers,
            "includes": includes,
            "defines": defines
        }

        filename = 'conandeps/{}/BUILD'.format(dependency.ref.name)
        content = Template(template).render(**context)
        save(filename, content)

        return filename

    def _create_new_local_repository(self, dependency, dependency_buildfile_name):
        snippet = textwrap.dedent("""
            native.new_local_repository(
                name="{}",
                path="{}",
                build_file="{}",
            )
        """).format(
            dependency.ref.name,
            dependency.package_folder,
            dependency_buildfile_name
        )

        return snippet

    def _save_dependencies_file(self, local_repositories):
        template = textwrap.dedent("""
            def load_conan_dependencies():
              {}
        """)

        function_content = "\n".join(local_repositories)
        function_content = textwrap.indent(function_content, '    ')
        content = template.format(function_content)

        # A BUILD file must exist, even if it's empty, in order for bazel
        # to detect it as a bazel package and allow to load the .bzl files
        save("conandeps/BUILD", "")

        save("conandeps/dependencies.bzl", content)
