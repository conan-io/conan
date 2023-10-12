import os
import textwrap
from collections import namedtuple

from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conans.model.dependencies import get_transitive_requires
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


def _get_package_name(dep, build_context_suffix=None):
    pkg_name = dep.cpp_info.get_property("bazel_module_name") or _get_package_reference_name(dep)
    suffix = _get_suffix(dep, build_context_suffix)
    return f"{pkg_name}{suffix}"


def _get_component_name(dep, comp_ref_name, build_context_suffix=None):
    pkg_name = _get_package_name(dep, build_context_suffix=build_context_suffix)
    if comp_ref_name not in dep.cpp_info.components:
        # foo::foo might be referencing the root cppinfo
        if _get_package_reference_name(dep) == comp_ref_name:
            return pkg_name
        raise ConanException("Component '{name}::{cname}' not found in '{name}' "
                             "package requirement".format(name=_get_package_reference_name(dep),
                                                          cname=comp_ref_name))
    comp_name = dep.cpp_info.components[comp_ref_name].get_property("bazel_module_name")
    suffix = _get_suffix(dep, build_context_suffix)
    comp_name = f"{comp_name}{suffix}" if comp_name else None
    # If user did not set bazel_module_name, let's create a component name
    # with a namespace, e.g., dep-comp1
    return comp_name or _get_name_with_namespace(pkg_name, comp_ref_name)


def _get_suffix(req, build_context_suffix=None):
    """
    Get the package name suffix coming from BazelDeps.build_context_suffix attribute, but only
    for requirements declared as build requirement.

    :param req: requirement ConanFile instance
    :param build_context_suffix: `dict` with all the suffixes
    :return: `str` with the suffix
    """
    if not build_context_suffix or not req.is_build_context:
        return ""
    return build_context_suffix.get(req.ref.name, "")


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


def _get_libs(conanfile, cpp_info, is_shared=False, relative_to_path=None) -> dict:
    """
    Get the static/shared library paths

    :param conanfile: The current recipe object.
    :param dep: <ConanFileInterface obj> of the dependency.
    :param cpp_info: <CppInfo obj> of the component.
    :param relative_to_path: base path to prune from each lib path
    :return: dict of static/shared library absolute paths -> {lib_name: (IS_SHARED, LIB_PATH, DLL_PATH)}
    """
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

    cpp_info = cpp_info
    libdirs = cpp_info.libdirs
    bindirs = cpp_info.bindirs
    libs = cpp_info.libs[:]  # copying the values
    ret = {}  # lib: (is_shared, lib_path, dll_path)

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
            if is_shared and ext == ".lib":
                dll_path = get_dll_file_paths(f"{name}.dll")
            ret.setdefault(lib, (is_shared,
                                 _relativize_path(lib_path, relative_to_path=relative_to_path),
                                 _relativize_path(dll_path, relative_to_path=relative_to_path)))

    conanfile.output.warning(f"The library/ies {libs} cannot be found in the dependency")
    return ret


def _get_headers(cpp_info, package_folder_path):
    return ', '.join('"{}/**"'.format(_relativize_path(path, package_folder_path))
                     for path in cpp_info.includedirs)


def _get_defines(cpp_info):
    return ', '.join('"{}"'.format(define.replace('"', '\\' * 3 + '"'))
                     for define in cpp_info.defines)


def _get_linkopts(cpp_info, os_build):
    link_opt = '"/DEFAULTLIB:{}"' if os_build == "Windows" else '"-l{}"'
    system_libs = [link_opt.format(lib) for lib in cpp_info.system_libs]
    shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags
    return ", ".join(system_libs + shared_flags)


def _get_copts(cpp_info):
    includedirsflags = ['-I"${}"'.format(d) for d in cpp_info.includedirs]
    cxxflags = [var.replace('"', '\\"') for var in cpp_info.cxxflags]
    cflags = [var.replace('"', '\\"') for var in cpp_info.cflags]
    return ", ".join(includedirsflags + cxxflags + cflags)


# FIXME: Very fragile. Need UTs, and, maybe, move it to conan.tools.files
def _relativize_path(path, relative_to_path):
    """
    Relativize the path with regard to a given base path

    :param path: path to relativize
    :param relative_to_path: base path to prune from the path
    :return: Unix-like path relative to ``relative_to_path``. Otherwise, it returns
             the Unix-like ``path``.
    """
    if not path or not relative_to_path:
        return path
    p = path.replace("\\", "/")
    rel = relative_to_path.replace("\\", "/")
    if p.startswith(rel):
        return p[len(rel):].lstrip("/")
    elif rel in p:
        return p.split(rel)[-1].lstrip("/")
    else:
        return p.lstrip("/")


def _get_package_folder(dep):
    # If editable, package_folder can be None
    root_folder = dep.recipe_folder if dep.package_folder is None \
        else dep.package_folder
    return root_folder.replace("\\", "/")


_DepInfo = namedtuple("DepInfo", ['name', 'requires', 'cpp_info'])


class _InfoGenerator:

    def __init__(self, conanfile, dep, build_context_suffix=None):
        self._conanfile = conanfile
        self._dep = dep
        self._build_context_suffix = build_context_suffix or {}
        self._transitive_reqs = get_transitive_requires(self._conanfile, dep)

    def _get_cpp_info_requires_names(self, cpp_info):
        """
        Get all the pkg valid names from the requires ones given a CppInfo object.

        For instance, those requires could be coming from:

        ```python
        from conan import ConanFile
        class PkgConan(ConanFile):
            requires = "other/1.0"

            def package_info(self):
                self.cpp_info.requires = ["other::cmp1"]

            # Or:

            def package_info(self):
                self.cpp_info.components["cmp"].requires = ["other::cmp1"]
        ```
        """
        dep_ref_name = _get_package_reference_name(self._dep)
        ret = []
        for req in cpp_info.requires:
            pkg_ref_name, comp_ref_name = req.split("::") if "::" in req else (dep_ref_name, req)
            # For instance, dep == "hello/1.0" and req == "other::cmp1" -> hello != other
            if dep_ref_name != pkg_ref_name:
                try:
                    req_conanfile = self._transitive_reqs[pkg_ref_name]
                except KeyError:
                    continue  # If the dependency is not in the transitive, might be skipped
            else:  # For instance, dep == "hello/1.0" and req == "hello::cmp1" -> hello == hello
                req_conanfile = self._dep
            comp_name = _get_component_name(req_conanfile, comp_ref_name, self._build_context_suffix)
            ret.append(comp_name)
        return ret

    @property
    def components_info(self):
        """
        Get the whole package and its components information like their own requires, names and even
        the cpp_info for each component.

        :return: `list` of `_PCInfo` objects with all the components information
        """
        if not self._dep.cpp_info.has_components:
            return []
        components_info = []
        # Loop through all the package's components
        for comp_ref_name, cpp_info in self._dep.cpp_info.get_sorted_components().items():
            # At first, let's check if we have defined some components requires, e.g., "dep::cmp1"
            comp_requires_names = self._get_cpp_info_requires_names(cpp_info)
            comp_name = _get_component_name(self._dep, comp_ref_name, self._build_context_suffix)
            # Save each component information
            components_info.append(_DepInfo(comp_name, comp_requires_names, cpp_info))
        return components_info

    @property
    def root_package_info(self):
        """
        Get the whole package information

        :return: `_PCInfo` object with the package information
        """
        pkg_name = _get_package_name(self._dep, self._build_context_suffix)
        # At first, let's check if we have defined some global requires, e.g., "other::cmp1"
        requires = self._get_cpp_info_requires_names(self._dep.cpp_info)
        # If we have found some component requires it would be enough
        if not requires:
            # If no requires were found, let's try to get all the direct dependencies,
            # e.g., requires = "other_pkg/1.0"
            requires = [_get_package_name(req, self._build_context_suffix)
                        for req in self._transitive_reqs.values()]
        cpp_info = self._dep.cpp_info
        return _DepInfo(pkg_name, requires, cpp_info)


class _BazelDependenciesBZLGenerator:
    """
    Bazel needs to know all the dependencies for its current project. So, the only way
    to do that is to tell the WORKSPACE file how to load all the Conan ones. This is the goal
    of the function created by this class, the ``load_conan_dependencies`` one.

    More information:
        * https://bazel.build/reference/be/workspace#new_local_repository
    """

    filename = "dependencies.bzl"
    template = textwrap.dedent("""\
        # This Bazel module should be loaded by your WORKSPACE file.
        # Add these lines to your WORKSPACE one (assuming that you're using the "bazel_layout"):
        # load("@//bazel-conan-tools:dependencies.bzl", "load_conan_dependencies")
        # load_conan_dependencies()

        {%- macro new_local_repository(pkg_name, pkg_folder, pkg_build_file_path) %}
            native.new_local_repository(
                name="{{pkg_name}}",
                path="{{pkg_folder}}",
                build_file="{{pkg_build_file_path}}",
            )
        {%- endmacro %}

        def load_conan_dependencies():
            {%- for pkg_name, pkg_folder, pkg_build_file_path in dependencies %}
            {{new_local_repository(pkg_name, pkg_folder, pkg_build_file_path)}}
            {%- endfor %}
        """)

    def __init__(self, conanfile, dependencies):
        self._conanfile = conanfile
        self._dependencies = dependencies

    def generate(self):
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(self._dependencies)
        # Saving the BUILD (empty) and dependencies.bzl files
        save(self.filename, content)
        save("BUILD.bazel", "# This is an empty BUILD file to be able to load the "
                            "dependencies.bzl one.")


class _BazelBUILDGenerator:

    # If both files exist, BUILD.bazel takes precedence over BUILD
    # https://bazel.build/concepts/build-files
    filename = "BUILD.bazel"
    template = textwrap.dedent("""
    load("@rules_cc//cc:defs.bzl", "cc_import", "cc_library")

    # Components precompiled libs
    {% for component_name, is_shared, lib_path, dll_path in components.libs %}
    cc_import(
        name = "{{ component_name }}_precompiled",
        static_library = "{{ lib_path }}",
        interface_library = "{{ lib_path }}",
        shared_library = "{{ dll_path }}",
    )
    {% endfor %}
    # Root package precompiled lib
    cc_import(
        name = "{{ pkg_name }}_precompiled",
        static_library = "{{ lib_path }}",
        interface_library = "{{ lib_path }}",
        shared_library = "{{ dll_path }}",
    )
    # Components libraries declaration
    {% for component_name, cpp_info in components.info %}
    cc_library(
        name = "{{ component_name }}",
        {% if headers %}
        hdrs = glob([{{ headers }}]),
        {% endif %}
        {% if defines %}
        defines = [{{ defines }}],
        {% endif %}
        {% if linkopts %}
        linkopts = [{{ linkopts }}],
        {% endif %}
        {% if copts %}
        copts = [{{ copts }}],
        {% endif %}
        visibility = ["//visibility:public"],
        {% if libs or shared_with_interface_libs %}
        deps = [
            {% for lib in libs %}
            ":{{ lib }}_precompiled",
            {% endfor %}
            {% for dep in dependencies %}
            "@{{ dep }}",
            {% endfor %}
        ],
        {% endif %}
    )
    {% endfor %}
    # Package library declaration
    cc_library(
        name = "{{ pkg["name"] }}",
        {% if headers %}
        hdrs = glob([{{ headers }}]),
        {% endif %}
        {% if defines %}
        defines = [{{ defines }}],
        {% endif %}
        {% if linkopts %}
        linkopts = [{{ linkopts }}],
        {% endif %}
        {% if copts %}
        copts = [{{ copts }}],
        {% endif %}
        visibility = ["//visibility:public"],
        {% if libs %}
        deps = [
            {% for lib in libs %}
            ":{{ lib }}_precompiled",
            {% endfor %}
            {% for dep in dependencies %}
            "@{{ dep }}",
            {% endfor %}
        ],
        {% endif %}
    )
    """)

    def __int__(self, conanfile, dep, build_context_suffix=None):
        self._conanfile = conanfile
        self._dep = dep
        self._build_context_suffix = build_context_suffix or {}

    @property
    def _is_shared_dependency(self):
        """
        Checking traits and shared option
        """
        default_value = self._dep.options.get_safe("shared") if self._dep.options else False
        return {"shared-library": True,
                "static-library": False}.get(str(self._dep.package_type), default=default_value)

    def _get_context(self, root_package_info, components_info):
        def fill_info(info):
            cpp_info = info.cpp_info
            headers = _get_headers(cpp_info, package_folder_path)
            copts = _get_copts(cpp_info)
            defines = _get_defines(cpp_info)
            linkopts = _get_linkopts(cpp_info, self._dep.settings_build.get_safe("os"))
            libs = _get_libs(self._conanfile, cpp_info, is_shared=is_shared,
                             relative_to_path=package_folder_path)
            return {
                "name": info.name,
                "libs": libs,
                "headers": headers,
                "defines": defines,
                "linkopts": linkopts,
                "copts": copts,
                "dependencies": info.requires
            }

        is_shared = self._is_shared_dependency
        package_folder_path = _get_package_folder(self._dep)
        context = dict()
        context["root"] = fill_info(root_package_info.cpp_info)
        context["components"] = []
        for component in components_info:
            context["components"].append(fill_info(component.cpp_info))
        return context

    def generate(self):
        info_generator = _InfoGenerator(self._conanfile, self._dep, self._build_context_suffix)
        root_package_info = info_generator.root_package_info
        components_info = info_generator.components_info
        context = self._get_context(root_package_info, components_info)
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(context)
        destination = os.path.join(root_package_info.name, self.filename)
        save(destination, content)
        return destination


class BazelDeps:

    def __init__(self, conanfile):
        self._conanfile = conanfile
        # Activate the build *.pc files for the specified libraries
        self.build_context_activated = []
        # If specified, the files/requires/names for the build context will be renamed appending
        # a suffix. It is necessary in case of same require and build_require and will cause an error
        self.build_context_suffix = {}

    def generate(self):
        """
        Save all the targets BUILD files and the dependencies.bzl one.

        Important! The dependencies.bzl file should be loaded by the WORKSPACE Bazel file.
        """
        check_duplicated_generator(self, self._conanfile)
        # Current directory is the generators_folder
        requirements = get_requirements(self._conanfile, self.build_context_activated,
                                        self.build_context_suffix)
        deps_info = []
        for require, dep in requirements:
            bazel_generator = _BazelBUILDGenerator(self._conanfile, dep,
                                              build_context_suffix=self.build_context_suffix)
            dest = bazel_generator.generate()
            deps_info.append({
                "name": _get_package_name(dep, self.build_context_suffix),
                "path": "",
                "build_file_path": ""
            })
        # dependencies.bzl has all the information
        bazel_dependencies_module_generator = _BazelDependenciesBZLGenerator(self._conanfile,
                                                                             deps_info)
        bazel_dependencies_module_generator.generate()



"""

The following are the typical use cases:
1. Linking a static library


cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  static_library = "libmylib.a",
  # If alwayslink is turned on,
  # libmylib.a will be forcely linked into any binary that depends on it.
  # alwayslink = 1,
)
2. Linking a shared library (Unix)

cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  shared_library = "libmylib.so",
)
3. Linking a shared library with interface library (Windows)

cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  # mylib.lib is an import library for mylib.dll which will be passed to linker
  interface_library = "mylib.lib",
  # mylib.dll will be available for runtime
  shared_library = "mylib.dll",
)
4. Linking a shared library with system_provided=True (Windows)

cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  # mylib.lib is an import library for mylib.dll which will be passed to linker
  interface_library = "mylib.lib",
  # mylib.dll is provided by system environment, for example it can be found in PATH.
  # This indicates that Bazel is not responsible for making mylib.dll available.
  system_provided = 1,
)
5. Linking to static or shared library
On Unix:

cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  static_library = "libmylib.a",
  shared_library = "libmylib.so",
)

# first will link to libmylib.a
cc_binary(
  name = "first",
  srcs = ["first.cc"],
  deps = [":mylib"],
  linkstatic = 1, # default value
)

# second will link to libmylib.so
cc_binary(
  name = "second",
  srcs = ["second.cc"],
  deps = [":mylib"],
  linkstatic = 0,
)
On Windows:

cc_import(
  name = "mylib",
  hdrs = ["mylib.h"],
  static_library = "libmylib.lib", # A normal static library
  interface_library = "mylib.lib", # An import library for mylib.dll
  shared_library = "mylib.dll",
)

# first will link to libmylib.lib
cc_binary(
  name = "first",
  srcs = ["first.cc"],
  deps = [":mylib"],
  linkstatic = 1, # default value
)

# second will link to mylib.dll through mylib.lib
cc_binary(
  name = "second",
  srcs = ["second.cc"],
  deps = [":mylib"],
  linkstatic = 0,
)
cc_import supports an include attribute. For example:

  cc_import(
  name = "curl_lib",
  hdrs = glob(["vendor/curl/include/curl/*.h"]),
  includes = [ "vendor/curl/include" ],
  shared_library = "vendor/curl/lib/.libs/libcurl.dylib",
)


"""
