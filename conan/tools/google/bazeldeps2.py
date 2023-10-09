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


def _get_libs(conanfile, dep, relative_to_path=None) -> dict:
    """
    Get the static/shared library paths

    :param conanfile: The current recipe object.
    :param dep: <ConanFileInterface obj> of the dependency.
    :param relative_to_path: base path to prune from each lib path
    :return: dict of static/shared library absolute paths -> {lib_name: (IS_SHARED, LIB_PATH, DLL_PATH)}
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

    cpp_info = dep.cpp_info.aggregated_components()  # dep.cpp_info
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
            ret.setdefault(lib, (shared,
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


def _get_linkopt(cpp_info, os_build):
    link_opt = '"/DEFAULTLIB:{}"' if os_build == "Windows" else '"-l{}"'
    system_libs = [link_opt.format(l) for l in cpp_info.system_libs]
    shared_flags = cpp_info.sharedlinkflags + cpp_info.exelinkflags
    return ", ".join(system_libs + shared_flags)


def _get_copt(cpp_info):
    includedirsflags = ['-I"${%s}"' % d for d in cpp_info.includedirs]
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


class _BazelDependenciesBZLGenerator:

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
        # Containing the [(pkg_name, pkg_folder, pkg_build_file_path), ...]
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

    filename = "BUILD.bazel"
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

    def _get_package_folder(self):
        # If editable, package_folder can be None
        root_folder = self._dep.recipe_folder if self._dep.package_folder is None \
            else self._dep.package_folder
        return root_folder.replace("\\", "/")

    def __int__(self, conanfile, dep, require):
        self._conanfile = conanfile
        self._dep = dep
        self._require = require

    @property
    def _context(self):
        cpp_info = self._dep.cpp_info
        package_folder_path = self._get_package_folder()
        headers = _get_headers(cpp_info, package_folder_path)
        copt = _get_copt(cpp_info)
        defines = _get_defines(cpp_info)
        linkopt = _get_linkopt(cpp_info, self._dep.settings_build.get_safe("os"))
        libs = _get_libs(self._conanfile, self._dep, package_folder_path)

        context = {
            "name": self._dep.ref.name,
            "libs": libs,
            "copt": copt,
            "libdir": lib_dir,
            "headers": headers,
            "defines": defines,
            "linkopts": linkopt,
            "dependencies": dependencies,
        }
        return context

    def generate(self):
        template = Template(self.template, trim_blocks=True, lstrip_blocks=True,
                            undefined=StrictUndefined)
        content = template.render(self._dependencies)
        # Saving the BUILD (empty) and dependencies.bzl files
        save(self.filename, content)


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
            bazel_generator = _BazelGenerator(self._conanfile, dep,
                                              build_context_suffix=self.build_context_suffix)
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
