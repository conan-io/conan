import textwrap

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
        dependency.new_cpp_info.aggregate_components()

        if not dependency.new_cpp_info.libs and not dependency.new_cpp_info.includedirs:
            return None

        result = 'load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")\n\n'

        for lib in dependency.new_cpp_info.libs:
            result += 'cc_import(\n'
            result += '    name = "{0}_precompiled",\n'.format(lib)
            result += '    static_library = "{0}/lib{1}.a"\n'.format(
                dependency.new_cpp_info.libdirs[0],
                lib
            )
            result += ')\n\n'

        result += 'cc_library(\n'
        result += '    name = "{}",\n'.format(dependency.ref.name)

        if dependency.new_cpp_info.includedirs:
            headers = []
            includes = []
            for path in dependency.new_cpp_info.includedirs:
                headers.append('"{}/**"'.format(path))
                includes.append('"{}"'.format(path))

            if headers:
                headers = ', '.join(headers)
                result += '    hdrs = glob([{}]),\n'.format(headers)

            if includes:
                includes = ', '.join(includes)
                result += '    includes = [{}],\n'.format(includes)

        if dependency.new_cpp_info.defines:
            defines = ('"{}"'.format(define) for define in dependency.new_cpp_info.defines)
            defines = ', '.join(defines)
            result += '    defines = [{}],\n'.format(defines)

        result += '    visibility = ["//visibility:public"]\n'
        result += ')\n'

        filename = 'conandeps/{}/BUILD'.format(dependency.ref.name)
        save(filename, result)

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

        # A BUILD file must exist, even if it's empty, in order to bazel
        # detect it as a bazel package and allow to load the .bzl files
        save("conandeps/BUILD", "")

        save("conandeps/dependencies.bzl", content)
