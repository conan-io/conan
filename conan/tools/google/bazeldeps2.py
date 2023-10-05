import os
import textwrap

from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conans.util.files import save


def _get_name_with_namespace(namespace, name):
    """
    Build a name with a namespace, e.g., openssl-crypto
    """
    return f"{namespace}-{name}"


def _get_package_reference_name(dep):
    """
    Get the reference name for the given package
    """
    return dep.ref.name


def _get_package_aliases(dep):
    pkg_aliases = dep.cpp_info.get_property("pkg_config_aliases")
    return pkg_aliases or []


def _get_component_aliases(dep, comp_name):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_name:
            return _get_package_aliases(dep)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_aliases = dep.cpp_info.components[comp_name].get_property("pkg_config_aliases")
    return comp_aliases or []


def _get_package_name(dep, build_context_suffix=None):
    pkg_name = dep.cpp_info.get_property("pkg_config_name") or _get_package_reference_name(dep)
    suffix = _get_suffix(dep, build_context_suffix)
    return f"{pkg_name}{suffix}"


def _get_component_name(dep, comp_name, build_context_suffix=None):
    if comp_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_name:
            return _get_package_name(dep, build_context_suffix)
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_name))
    comp_name = dep.cpp_info.components[comp_name].get_property("pkg_config_name")
    suffix = _get_suffix(dep, build_context_suffix)
    return f"{comp_name}{suffix}" if comp_name else None


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


def get_libs(conanfile, dep, relative_to=None) -> dict:
    """
    Get the static/shared library paths

    :param conanfile: The current recipe object.
    :param dep: <ConanFileInterface obj> of the dependency.
    :param relative_to: path to any folder to relativize the absolute path
    :return: tuple of static/shared library absolute paths -> (static_path, shared_path)
    """
    def is_shared_dependency():
        """
        Checking traits and shared option
        """
        default_value = dep.options.get_safe("shared") if dep.options else False
        return {"shared-library": True,
                "static-library": False}.get(str(dep.package_type), default=default_value)

    def get_dll_file_paths(expected_file) -> str:
        """
        (Windows platforms only) Find a given DLL file in bin directories.
        If found return the full path, otherwise return "".
        """
        for bin_file in bindirs:
            if not os.path.exists(bin_file):
                conanfile.output.debug(f"The bin folder doesn't exist: {bin_file}")
                continue
            for f in os.listdir(bin_file):
                full_path = os.path.join(bin_file, f)
                if not os.path.isfile(full_path):
                    continue
                if f == expected_file:
                    return full_path
        conanfile.output.debug(f"It was not possible to find the {expected_file} file.")
        return ""

    cpp_info = dep.cpp_info  # dep.cpp_info.aggregated_components()
    shared = is_shared_dependency()
    libdirs = cpp_info.libdirs
    bindirs = cpp_info.bindirs
    libs = cpp_info.libs[:]  # copying the values
    ret = {}  # lib: (is_shared, lib_path, interface_lib_path)

    for libdir in libdirs:
        lib = ""
        if not os.path.exists(libdir):
            conanfile.output.debug("The library folder doesn't exist: {}".format(libdir))
            continue
        files = os.listdir(libdir)
        lib_basename = None
        lib_path = None
        for f in files:
            full_path = os.path.join(libdir, f)
            if not os.path.isfile(full_path):  # Make sure that directories are excluded
                continue
            # Users may not name their libraries in a conventional way. For example, directly
            # use the basename of the lib file as lib name.
            if f in libs:
                lib = f
                libs.remove(f)
                lib_basename = f
                lib_path = full_path
                break
            name, ext = os.path.splitext(f)
            if ext in (".so", ".a", ".dylib", ".bc"):
                if name.startswith("lib"):
                    name = name[3:]
            if name in libs:
                lib = name
                libs.remove(name)
                lib_basename = f
                lib_path = full_path
                break
        if lib_path is not None:
            name, ext = os.path.splitext(lib_basename)
            # Windows case: DLL stored in bindirs and .lib == interface
            dll_path = ""
            if shared and ext == ".lib":
                dll_path = get_dll_file_paths(f"{name}.dll")
            ret.setdefault(lib, (shared, lib_path, dll_path))

    conanfile.output.warning(f"The library/ies {libs} cannot be found in the dependency")
    return ret


class _BazelDependenciesBZLGenerator:

    filename = "dependencies.bzl"
    template = textwrap.dedent("""\
        # This Bazel module should be loaded by your WORKSPACE file.
        # Add these lines to your WORKSPACE one (assuming that you're using the "bazel_layout"):
        # load("@//bazel-conan-tools:dependencies.bzl", "load_conan_dependencies")
        # load_conan_dependencies()

        {%- macro new_local_repository(pkg_name, pkg_folder, pkg_build_file_path) -%}
            native.new_local_repository(
                name="{{pkg_name}}",
                path="{{pkg_folder}}",
                build_file="{{pkg_build_file_path}}",
            )
        {%- endmacro -%}

        def load_conan_dependencies():
            {% for pkg_name, pkg_folder, pkg_build_file_path in dependencies %}
            {{new_local_repository(pkg_name, pkg_folder, pkg_build_file_path)}}
            {% endfor %}
        """)

    def __init__(self, conanfile, dependencies):
        self._conanfile = conanfile
        # Containing the [(pkg_name, pkg_folder, pkg_build_file_path), ...]
        self._dependencies = dependencies

    def generate(self):
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(self._dependencies)
        # Saving the BUILD (empty) and dependencies.bzl files
        save(self.filename, content)
        save("BUILD", "# This is an empty BUILD file to be able to load the dependencies.bzl one.")


class _BazelBUILDGenerator:

    template = textwrap.dedent("""
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


class _BazelGenerator:

    def __init__(self, conanfile, dep, require):
        self._conanfile = conanfile
        self._dep = dep
        self._require = require

    @property
    def bazel_files(self):
        ret = {}
        return ret


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
        bazel_files = {}
        for require, dep in requirements:
            bazel_generator = _BazelGenerator(self._conanfile, dep, build_context_suffix=self.build_context_suffix)
            bazel_files.update(bazel_generator.bazel_files)
        return bazel_files

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
