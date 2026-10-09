"""
Creates a ``conan_bzl.rc`` file which defines a ``conan-config`` configuration with the flags from
the profile and the conf, plus host and target platforms. For gcc and clang on Linux it also writes
a ``cc_toolchain`` in ``conan_toolchain/BUILD.bazel``. That toolchain is how Bazel runs the compiler
from the profile. The same rule is used for a native build and a cross build. A cross build adds a
second one for the build profile.

A platform is the host or target machine. Toolchain resolution uses it to select the compiler.
Platform based resolution is the default since Bazel 7. ``--cpu`` and ``--crosstool_top`` are the
older selection flags.

More information related:
    * Platforms: https://bazel.build/concepts/platforms
    * Toolchains: https://bazel.build/extending/toolchains
    * Issue related: https://github.com/bazelbuild/bazel/issues/6516

Others:
    * CROOSTOOL: https://github.com/bazelbuild/bazel/blob/cb0fb033bad2a73e0457f206afb87e195be93df2/tools/cpp/CROSSTOOL
    * Cross-compiling with Bazel: https://ltekieli.com/cross-compiling-with-bazel/
    * bazelrc files: https://bazel.build/run/bazelrc
    * CLI options: https://bazel.build/reference/command-line-reference
    * User manual: https://bazel.build/docs/user-manual
"""
import json
import os
import shutil
import subprocess
import textwrap

from jinja2 import Environment, Template

from conan.api.output import Color
from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.graph.graph import RECIPE_CONSUMER, RECIPE_EDITABLE
from conan.internal.internal_tools import raise_on_universal_arch
from conan.tools.build.flags import (architecture_flag, architecture_link_flag, cppstd_flag,
                                     libcxx_flags)
from conan.tools.files import save


# Conan settings value to @platforms constraint name.
# https://github.com/bazelbuild/platforms
_OS_CONSTRAINTS = {
    "Linux": "linux",
    "Windows": "windows",
    "Macos": "osx",
    "Android": "android",
    "iOS": "ios",
    "FreeBSD": "freebsd",
    "watchOS": "watchos",
    "tvOS": "tvos",
    "visionOS": "visionos",
    "Emscripten": "emscripten",
    "VxWorks": "vxworks",
    "AIX": "aix",
    "Neutrino": "qnx",
    "baremetal": "none",
}
_ARCH_CONSTRAINTS = {
    "x86": "x86_32",
    "x86_64": "x86_64",
    "armv7": "armv7",
    "armv7hf": "armv7",
    "armv8": "aarch64",
    "ppc64le": "ppc64le",
    "s390x": "s390x",
    "riscv64": "riscv64",
}
# Newest release on https://registry.bazel.build whose presubmit.yml lists Bazel 7, 8 and 9.
# The file is modules/<name>/<version>/presubmit.yml in bazelbuild/bazel-central-registry.
_PLATFORMS_VERSION = "1.1.0"
# Same version BazelDeps writes. Bazel 7, 8 and 9 accept it.
_RULES_CC_VERSION = "0.2.17"
_TOOLCHAIN_PACKAGE = "conan_toolchain"
_MODULE_FILENAME = "conan_toolchain.MODULE.bazel"
# settings.compiler -> (c driver, c++ driver). compiler_executables overrides these.
_UNIX_COMPILERS = {
    "gcc": ("gcc", "g++"),
    "clang": ("clang", "clang++"),
}
# unix_cc_toolchain_config reads llvm-cov and objcopy unconditionally.
_BINUTILS = ("ar", "nm", "objdump", "strip", "objcopy", "gcov", "dwp", "llvm-cov")


def _generators_parts(conanfile):
    folder = conanfile.folders.generators or ""
    return [part for part in folder.replace("\\", "/").split("/") if part and part != "."]


def _platform_constraints(settings):
    os_name = settings.get_safe("os")
    arch = settings.get_safe("arch")
    os_constraint = _OS_CONSTRAINTS.get(os_name)
    arch_constraint = _ARCH_CONSTRAINTS.get(arch)
    if not os_constraint or not arch_constraint:
        return None
    return [f"@platforms//os:{os_constraint}", f"@platforms//cpu:{arch_constraint}"]


def _platform_rule(name, constraints):
    values = "\n".join(f'        "{constraint}",' for constraint in constraints)
    return (
        "platform(\n"
        f'    name = "{name}",\n'
        "    constraint_values = [\n"
        f"{values}\n"
        "    ],\n"
        ")"
    )


def _is_consumer(conanfile):
    try:
        return conanfile._conan_node.recipe in (RECIPE_CONSUMER, RECIPE_EDITABLE)
    except AttributeError:
        return False


class _ProfileView:
    """settings and conf pair. The flag helpers read both off the conanfile."""

    def __init__(self, settings, conf):
        self.settings = settings
        self.conf = conf


def _slash(path):
    return path.replace("\\", "/")


def _tool_path(name):
    """Keep a path. Resolve a bare name on PATH.

    Bazel uses the string as a path. It does not search PATH.
    """
    normalized = _slash(name)
    if "/" in normalized or os.path.isabs(name):
        return normalized
    found = shutil.which(name)
    return _slash(found) if found else None


def _sibling(compiler_path, tool):
    """ar and the rest sit next to the compiler and keep its prefix."""
    folder, _, name = compiler_path.rpartition("/")
    stem = name
    for suffix in ("clang++", "g++", "clang", "gcc"):
        if name == suffix or name.endswith("-" + suffix):
            stem = name[:-len(suffix)]
            break
    sibling = f"{stem}{tool}"
    return f"{folder}/{sibling}" if folder else sibling


def _resolve_drivers(conanfile, settings, conf):
    """Return (c path, c++ path) for a Linux gcc or clang profile, or None."""
    compiler = settings.get_safe("compiler")
    if settings.get_safe("os") != "Linux" or compiler not in _UNIX_COMPILERS:
        return None
    executables = conf.get("tools.build:compiler_executables", default={}, check_type=dict) or {}
    c_default, cpp_default = _UNIX_COMPILERS[compiler]
    # A missing entry uses the default driver name. Set both when the names differ.
    c_path = _tool_path(executables.get("c") or c_default)
    cpp_path = _tool_path(executables.get("cpp") or cpp_default)
    if not c_path or not cpp_path:
        conanfile.output.warning(
            "BazelToolchain could not find the compiler executable. "
            "Set tools.build:compiler_executables or make the compiler available on PATH."
        )
        return None
    return c_path, cpp_path


def _builtin_includes(compiler):
    if not compiler or not os.path.isfile(compiler):
        return []
    try:
        proc = subprocess.run(
            [compiler, "-E", "-v", "-x", "c++", "-"],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    text = (proc.stderr or b"").decode("utf-8", "replace")
    text += (proc.stdout or b"").decode("utf-8", "replace")
    includes = []
    capture = False
    for line in text.splitlines():
        if line.startswith("#include <...>"):
            capture = True
            continue
        if line.startswith("End of search list"):
            break
        if capture:
            path = line.strip()
            if path:
                includes.append(_slash(path))
    return includes


def _translated_flags(settings, conf):
    """Architecture and libcxx flags, the same helpers CMakeToolchain uses."""
    view = _ProfileView(settings, conf)
    lib, define = libcxx_flags(view)
    arch = architecture_flag(view) or ""
    arch_link = architecture_link_flag(view) or ""
    compile_flags = []
    cxx_flags = []
    link_flags = []
    if arch:
        compile_flags.append(arch)
        link_flags.append(arch)
    if define:
        compile_flags.append(f"-D{define}")
    if lib:
        cxx_flags.append(lib)
        link_flags.append(lib)
    if arch_link:
        link_flags.append(arch_link)
    return compile_flags, cxx_flags, link_flags


def _starlark(value):
    """A Starlark literal. Lists and dicts are expanded. Strings are quoted."""
    if isinstance(value, dict):
        body = [f"        {json.dumps(key)}: {json.dumps(item)}," for key, item in value.items()]
        return "{\n" + "\n".join(body) + "\n    }" if body else "{}"
    if isinstance(value, (list, tuple)):
        body = [f"        {json.dumps(item)}," for item in value]
        return "[\n" + "\n".join(body) + "\n    ]" if body else "[]"
    return json.dumps(value)


_env = Environment(trim_blocks=True, lstrip_blocks=True)
_env.filters["starlark"] = _starlark
_TOOLCHAIN_TEMPLATE = _env.from_string(textwrap.dedent("""\
    cc_toolchain_config(
        name = "{{ name }}_config",
        cpu = {{ cpu|starlark }},
        compiler = {{ compiler|starlark }},
        toolchain_identifier = "conan_{{ name }}",
        host_system_name = "local",
        target_system_name = "local",
        target_libc = "unknown",
        abi_version = "unknown",
        abi_libc_version = "unknown",
        tool_paths = {{ tool_paths|starlark }},
        cxx_builtin_include_directories = {{ includes|starlark }},
        {% if compile_flags %}
        compile_flags = {{ compile_flags|starlark }},
        {% endif %}
        {% if cxx_flags %}
        cxx_flags = {{ cxx_flags|starlark }},
        {% endif %}
        {% if link_flags %}
        link_flags = {{ link_flags|starlark }},
        {% endif %}
        {% if sysroot %}
        builtin_sysroot = {{ sysroot|starlark }},
        {% endif %}
    )

    cc_toolchain(
        name = "{{ name }}_cc",
        toolchain_identifier = "conan_{{ name }}",
        toolchain_config = ":{{ name }}_config",
        all_files = ":empty",
        compiler_files = ":empty",
        dwp_files = ":empty",
        linker_files = ":empty",
        objcopy_files = ":empty",
        strip_files = ":empty",
        supports_param_files = 0,
    )

    toolchain(
        name = "cc_for_{{ name }}",
        toolchain = ":{{ name }}_cc",
        toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
        exec_compatible_with = {{ exec_constraints|starlark }},
        target_compatible_with = {{ target_constraints|starlark }},
    )"""))


def _toolchain_rules(name, cpu, compiler, drivers, includes, compile_flags, cxx_flags, link_flags,
                     sysroot, exec_constraints, target_constraints):
    c_path, cpp_path = drivers
    tool_paths = {"gcc": c_path, "cpp": cpp_path, "ld": cpp_path}
    for tool in _BINUTILS:
        tool_paths[tool] = _sibling(c_path, tool)
    return _TOOLCHAIN_TEMPLATE.render(
        name=name,
        cpu=cpu,
        compiler=compiler,
        tool_paths=tool_paths,
        includes=includes,
        compile_flags=compile_flags,
        cxx_flags=cxx_flags,
        link_flags=link_flags,
        sysroot=sysroot,
        exec_constraints=exec_constraints,
        target_constraints=target_constraints,
    )


class BazelToolchain:
    bazelrc_name = "conan_bzl.rc"
    bazelrc_config = "conan-config"
    bazelrc_template = textwrap.dedent("""\
    # Automatic bazelrc file created by Conan
    {% if copt %}build:conan-config {{copt}}{% endif %}
    {% if conlyopt %}build:conan-config {{conlyopt}}{% endif %}
    {% if cxxopt %}build:conan-config {{cxxopt}}{% endif %}
    {% if linkopt %}build:conan-config {{linkopt}}{% endif %}
    {% if force_pic %}build:conan-config --force_pic={{force_pic}}{% endif %}
    {% if dynamic_mode %}build:conan-config --dynamic_mode={{dynamic_mode}}{% endif %}
    {% if compilation_mode %}build:conan-config --compilation_mode={{compilation_mode}}{% endif %}
    {% if compiler %}build:conan-config --compiler={{compiler}}{% endif %}
    {% if cpu %}build:conan-config --cpu={{cpu}}{% endif %}
    {% if crosstool_top %}build:conan-config --crosstool_top={{crosstool_top}}{% endif %}""")

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        raise_on_universal_arch(conanfile)

        self._conanfile = conanfile

        # Bazel build parameters
        shared = self._conanfile.options.get_safe("shared")
        fpic = self._conanfile.options.get_safe("fPIC")
        #: Boolean used to add --force_pic=True. Depends on self.options.shared and
        #: self.options.fPIC values
        self.force_pic = fpic if (not shared and fpic is not None) else None
        # FIXME: Keeping this option but it's not working as expected. It's not creating the shared
        #        libraries at all.
        #: String used to add --dynamic_mode=["fully"|"off"]. Depends on self.options.shared value.
        self.dynamic_mode = "fully" if shared else "off"
        #: String used to add --cppstd=[FLAG]. Depends on your settings.
        self.cppstd = cppstd_flag(self._conanfile)
        #: List of flags used to add --copt=flag1 ... --copt=flagN
        self.copt = []
        #: List of flags used to add --conlyopt=flag1 ... --conlyopt=flagN
        self.conlyopt = []
        #: List of flags used to add --cxxopt=flag1 ... --cxxopt=flagN
        self.cxxopt = []
        #: List of flags used to add --linkopt=flag1 ... --linkopt=flagN
        self.linkopt = []
        #: String used to add --compilation_mode=["opt"|"dbg"]. Depends on self.settings.build_type
        self.compilation_mode = {'Release': 'opt', 'Debug': 'dbg'}.get(
            self._conanfile.settings.get_safe("build_type")
        )
        # Be aware that this parameter does not admit a compiler absolute path
        # If you want to add it, you will have to use a specific Bazel toolchain
        #: String used to add --compiler=xxxx.
        self.compiler = None
        #: String used to add --cpu=xxxxx. Left unset. Bazel 6 was the last release that needed it.
        self.cpu = None
        # This is itself a toolchain but just in case
        #: String used to add --crosstool_top.
        self.crosstool_top = None
        # TODO: Have a look at https://bazel.build/reference/be/make-variables
        # FIXME: Missing host_xxxx options. When are they needed? Cross-compilation?

    @staticmethod
    def _filter_list_empty_fields(v):
        return list(filter(bool, v))

    @property
    def cxxflags(self):
        ret = [self.cppstd]
        conf_flags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        ret = ret + self.cxxopt + conf_flags
        return self._filter_list_empty_fields(ret)

    @property
    def cflags(self):
        conf_flags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        ret = self.conlyopt + conf_flags
        return self._filter_list_empty_fields(ret)

    @property
    def ldflags(self):
        conf_flags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[],
                                              check_type=list)
        conf_flags.extend(self._conanfile.conf.get("tools.build:exelinkflags", default=[],
                                                   check_type=list))
        linker_scripts = self._conanfile.conf.get("tools.build:linker_scripts", default=[], check_type=list)
        conf_flags.extend(["-T'" + linker_script + "'" for linker_script in linker_scripts])
        ret = self.linkopt + conf_flags
        return self._filter_list_empty_fields(ret)

    def _rc_path(self):
        parts = _generators_parts(self._conanfile)
        return "/".join(parts + [self.bazelrc_name])

    def _context(self):
        return {
            "copt": " ".join(f"--copt={flag}" for flag in self.copt),
            "conlyopt": " ".join(f"--conlyopt={flag}" for flag in self.cflags),
            "cxxopt": " ".join(f"--cxxopt={flag}" for flag in self.cxxflags),
            "linkopt": " ".join(f"--linkopt={flag}" for flag in self.ldflags),
            "force_pic": self.force_pic,
            "dynamic_mode": self.dynamic_mode,
            "compilation_mode": self.compilation_mode,
            "compiler": self.compiler,
            "cpu": self.cpu,
            "crosstool_top": self.crosstool_top,
        }

    def _constraints(self, settings):
        os_name = settings.get_safe("os")
        arch = settings.get_safe("arch")
        if os_name is None or arch is None:
            return None
        constraints = _platform_constraints(settings)
        if constraints is None:
            raise ConanException(
                f"Cannot map os={os_name!r} arch={arch!r} to Bazel platform constraints."
            )
        return constraints

    def _rc_content(self, platform_lines):
        content = Template(self.bazelrc_template).render(self._context())
        if content and not content.endswith("\n"):
            content += "\n"
        return content + "\n".join(platform_lines) + "\n"

    def _describe_toolchain(self, name, settings, conf, exec_constraints, target_constraints):
        drivers = _resolve_drivers(self._conanfile, settings, conf)
        if drivers is None:
            return None
        includes = _builtin_includes(drivers[1])
        if os.path.isfile(drivers[1]) and not includes:
            self._conanfile.output.warning(
                "BazelToolchain could not detect builtin include directories from "
                f"{drivers[1]}. System headers may be rejected by the Bazel sandbox."
            )
        compile_flags, cxx_flags, link_flags = _translated_flags(settings, conf)
        sysroot = conf.get("tools.build:sysroot")
        sysroot = _slash(sysroot) if sysroot else None
        cpu = _ARCH_CONSTRAINTS.get(settings.get_safe("arch"), settings.get_safe("arch"))
        return _toolchain_rules(
            name, cpu, settings.get_safe("compiler"), drivers, includes,
            compile_flags, cxx_flags, link_flags, sysroot,
            exec_constraints, target_constraints,
        )

    def _write_platforms(self, exec_constraints, target_constraints):
        parts = _generators_parts(self._conanfile)
        folder_name = _TOOLCHAIN_PACKAGE
        package = "//" + "/".join(parts + [folder_name])
        sections = [
            _platform_rule("host", exec_constraints),
            _platform_rule("target", target_constraints),
        ]
        registered = []
        target_rules = self._describe_toolchain(
            "target", self._conanfile.settings, self._conanfile.conf,
            exec_constraints, target_constraints,
        )
        if target_rules:
            registered.append("cc_for_target")
            sections.append(target_rules)
        if exec_constraints != target_constraints and self._conanfile.conf_build:
            host_rules = self._describe_toolchain(
                "host", self._conanfile.settings_build, self._conanfile.conf_build,
                exec_constraints, exec_constraints,
            )
            if host_rules:
                registered.append("cc_for_host")
                sections.append(host_rules)
        if registered:
            header = textwrap.dedent("""\
                load("@bazel_tools//tools/cpp:unix_cc_toolchain_config.bzl", "cc_toolchain_config")
                load("@rules_cc//cc/toolchains:cc_toolchain.bzl", "cc_toolchain")

                package(default_visibility = ["//visibility:public"])
                """)
            build = header + "\n" + "\n\n".join(sections[:2]) + '\n\nfilegroup(name = "empty")\n\n'
            build += "\n\n".join(sections[2:]) + "\n"
        else:
            build = "\n\n".join(sections) + "\n"
        deps = [f'bazel_dep(name = "platforms", version = "{_PLATFORMS_VERSION}")']
        if registered:
            deps.append(f'bazel_dep(name = "rules_cc", version = "{_RULES_CC_VERSION}")')
            labels = "\n".join(f'    "{package}:{name}",' for name in registered)
            deps.append(f"register_toolchains(\n{labels}\n)")
        save(self._conanfile, os.path.join(folder_name, "BUILD.bazel"), build)
        save(self._conanfile, "BUILD.bazel", "# This is an empty BUILD file.")
        folder = "/".join(parts)
        include = f"//{folder}:{_MODULE_FILENAME}" if folder else f"//:{_MODULE_FILENAME}"
        module = (
            "# Generated by BazelToolchain. Include in your MODULE.bazel file with:\n"
            f'# include("{include}")\n'
            "\n"
            + "\n".join(deps)
            + "\n"
        )
        save(self._conanfile, _MODULE_FILENAME, module)
        return [
            f"build:{self.bazelrc_config} --platforms={package}:target",
            f"build:{self.bazelrc_config} --host_platform={package}:host",
        ]

    def generate(self):
        """
        Creates a ``conan_bzl.rc`` file with one ``conan-config`` configuration. Pass
        ``--config=conan-config`` to use it. The build type is ``--compilation_mode`` inside
        that config. A later install overwrites the file.

        Also writes host and target ``platform()`` rules and a ``conan_toolchain.MODULE.bazel``
        snippet when both profiles define ``os`` and ``arch``. For gcc and clang on Linux it writes
        the ``cc_toolchain`` that Bazel uses for that profile.
        """
        check_duplicated_generator(self, self._conanfile)
        exec_constraints = self._constraints(self._conanfile.settings_build)
        target_constraints = self._constraints(self._conanfile.settings)
        platform_lines = []
        if exec_constraints and target_constraints:
            platform_lines = self._write_platforms(exec_constraints, target_constraints)
        save(self._conanfile, BazelToolchain.bazelrc_name, self._rc_content(platform_lines))
        self._conanfile.output.info(f"BazelToolchain generated: {self.bazelrc_name}")
        rc_path = self._rc_path()
        if _is_consumer(self._conanfile):
            config = self.bazelrc_config
            msg = textwrap.dedent(f"""\
                BazelToolchain: Config '{config}' added to {rc_path}.
                    bazel --bazelrc={rc_path} build --config={config} //...
                    Or add to .bazelrc: try-import %workspace%/{rc_path}
                    bazel build --config={config} //...""")
            self._conanfile.output.info(msg, fg=Color.CYAN)
