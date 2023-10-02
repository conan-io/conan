import textwrap

from jinja2 import Template

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conans.util.files import save


# FIXME: This function should be a common one to be used by PkgConfigDeps, CMakeDeps?, etc.
def get_requirements(conanfile, build_context_activated, build_context_suffix):
    """
    Simply save the activated requirements (host + build + test), and the deactivated ones
    """
    def validate_build_requires(hreqs, breqs, activated, suffixes):
        """
        Check if any package exists at host and build context at the same time, and
        it doesn't have any suffix to avoid any name collisions

        :param hreqs: list of host requires
        :param breqs: list of build requires
        :param activated: list of activated build requires
        :param suffixes: dict of each build require and its suffix
        """
        activated_br = {r.ref.name for r in breqs.values()
                        if r.ref.name in activated}
        common_names = {r.ref.name for r in hreqs.values()}.intersection(activated_br)
        without_suffixes = [common_name for common_name in common_names
                            if suffixes.get(common_name) is None]
        if without_suffixes:
            raise ConanException(
                f"The packages {without_suffixes} exist both as 'require' and as"
                f" 'build require'. You need to specify a suffix using the "
                f"'build_context_suffix' attribute at the generator class.")

    # All the requirements
    host_req = conanfile.dependencies.host
    build_req = conanfile.dependencies.build  # tool_requires
    test_req = conanfile.dependencies.test

    # Check if it exists both as require and as build require without a suffix
    validate_build_requires(host_req, build_req,
                            build_context_activated, build_context_suffix)

    for require, dep in list(host_req.items()) + list(build_req.items()) + list(test_req.items()):
        # Require is not used at the moment, but its information could be used,
        # and will be used in Conan 2.0
        # Filter the build_requires not activated with self.build_context_activated
        if require.build and dep.ref.name not in build_context_activated:
            continue
        yield require, dep


class BazelDeps:

    library_BUILD_template = textwrap.dedent("""
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
    dependencies_bzl_template = textwrap.dedent("""
    # This Bazel module should be loaded by your WORKSPACE file.
    # Add these lines to your WORKSPACE one (assuming that you're using the "bazel_layout"):
    # load("@//bazel-conan-tools:dependencies.bzl", "load_conan_dependencies")
    # load_conan_dependencies()

    {%- macro new_local_repository(pkg_name, package_folder, build_file_path) -%}
        native.new_local_repository(
            name="{{pkg_name}}",
            path="{{package_folder}}",
            build_file="{{build_file_path}}",
        )
    {%- endmacro -%}

    def load_conan_dependencies():
        {% for pkg_name, package_folder, build_file_path in dependencies %}
        {{new_local_repository(pkg_name, package_folder, build_file_path)}}
        {% endfor %}
    """)

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build *.pc files for the specified libraries
        self.build_context_activated = []
        # If specified, the files/requires/names for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        self.build_context_suffix = {}

    @property
    def content(self):
        requirements = get_requirements(self._conanfile, self.build_context_activated,
                                        self.build_context_suffix)

        for require, dep in requirements:

            pc_generator = _PCGenerator(self._conanfile, dep, build_context_suffix=self.build_context_suffix)
            pc_files.update(pc_generator.pc_files)
        return pc_files

    def generate(self):
        """
        Save all the targets BUILD files and the dependencies.bzl one.

        Important! The dependencies.bzl file should be loaded by the WORKSPACE Bazel file.
        """
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        generator_files = self.content
        for generator_file, content in generator_files.items():
            save(generator_file, content)
