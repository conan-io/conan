"""
Creates a ``conan_bzl.rc`` file which defines a ``conan-config`` configuration with the flags from
the profile and the conf, plus host and target platforms. For gcc and clang on Linux, and for msvc
on Windows, it also writes a ``cc_toolchain`` in ``conan_toolchain/BUILD.bazel``. That
toolchain is how Bazel runs the compiler from the profile. The same rule is used for a native build
and a cross build. A cross build adds a second one for the build profile.

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
import posixpath
import re
import shutil
import textwrap

from jinja2 import Environment, Template

from conan.api.output import Color
from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.internal_tools import raise_on_universal_arch
from conan.internal.util.runners import check_output_runner, detect_runner
from conan.tools.build import stdcpp_library
from conan.tools.build.flags import (architecture_flag, architecture_link_flag, cppstd_flag,
                                     libcxx_flags)
from conan.tools.cmake.layout import is_consumer
from conan.tools.files import save
from conan.tools.microsoft import is_msvc_static_runtime
from conan.tools.microsoft.visual import _vcvars_call


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
_TOOLCHAIN_PACKAGE = "conan_toolchain"
_MODULE_FILENAME = "conan_toolchain.MODULE.bazel"
# The rules_cc copy of the windows config is the one with archiver_flags and default_link_flags.
_CONFIG_RULES = {
    "unix_cc_toolchain_config": "@bazel_tools//tools/cpp:unix_cc_toolchain_config.bzl",
    "windows_cc_toolchain_config":
        "@rules_cc//cc/private/toolchain:windows_cc_toolchain_config.bzl",
}
# settings.compiler -> (c driver, c++ driver). compiler_executables overrides these.
_UNIX_COMPILERS = {
    "gcc": ("gcc", "g++"),
    "clang": ("clang", "clang++"),
}
# unix_cc_toolchain_config reads llvm-cov and objcopy unconditionally.
_BINUTILS = ("ar", "nm", "objdump", "strip", "objcopy", "gcov", "dwp", "llvm-cov")
# --compilation_mode flags of the toolchain Bazel autodetects on Linux.
_UNIX_MODE_FLAGS = {
    "dbg_compile_flags": ["-g"],
    "opt_compile_flags": ["-g0", "-O2", "-DNDEBUG", "-ffunction-sections", "-fdata-sections"],
    "opt_link_flags": ["-Wl,--gc-sections"],
}
# The cross prefix of a driver, "aarch64-linux-gnu-" in "aarch64-linux-gnu-gcc-13".
_DRIVER_PREFIX = re.compile(r"(.*-)?(?:gcc|g\+\+|clang|clang\+\+)(?:-[\d.]+)?$")
# Conan arch -> link.exe / lib.exe /MACHINE value. The config cpu stays x64_windows.
_MSVC_MACHINE = {
    "x86_64": "X64",
    "x86": "X86",
    "armv7": "ARM",
    "armv8": "ARM64",
}
_MSVC_ASSEMBLER = {
    "X64": "ml64.exe",
    "X86": "ml.exe",
}


class _ProfileView:
    """One profile seen as a conanfile. The flag and vcvars helpers read these attributes."""

    def __init__(self, settings, conf, settings_build=None):
        self.settings = settings
        self.conf = conf
        self.settings_build = settings_build


def _slash(path):
    return path.replace("\\", "/")


def _flags(*flags):
    return [flag for flag in flags if flag]


def _platform_constraints(settings):
    """The @platforms constraints of a profile. None when it has no os or arch."""
    os_name, arch = settings.get_safe("os"), settings.get_safe("arch")
    if os_name is None or arch is None:
        return None
    if os_name not in _OS_CONSTRAINTS or arch not in _ARCH_CONSTRAINTS:
        raise ConanException(
            f"Cannot map os={os_name!r} arch={arch!r} to Bazel platform constraints."
        )
    return [f"@platforms//os:{_OS_CONSTRAINTS[os_name]}",
            f"@platforms//cpu:{_ARCH_CONSTRAINTS[arch]}"]


def _tool_path(name):
    """Keep a path. Resolve a bare name on PATH.

    Bazel uses the string as a path. It does not search PATH.
    """
    if "/" in _slash(name) or os.path.isabs(name):
        return _slash(name)
    found = shutil.which(name)
    return _slash(found) if found else None


def _compiler_executables(conf):
    return conf.get("tools.build:compiler_executables", default={}, check_type=dict)


def _binutil(driver, tool):
    """ar and the rest sit next to the driver and keep its cross prefix."""
    folder, name = posixpath.split(driver)
    match = _DRIVER_PREFIX.match(name)
    prefix = (match.group(1) or "") if match else ""
    return posixpath.join(folder, prefix + tool)


def _builtin_includes(conanfile, driver):
    """System include folders of a gcc or clang driver. The Bazel sandbox rejects the others."""
    if not os.path.isfile(driver):
        return []
    _, output = detect_runner(f'"{driver}" -E -v -x c++ {os.devnull}')
    listing = output.partition("#include <...> search starts here:")[2]
    listing = listing.partition("End of search list.")[0]
    includes = [_slash(line.strip()) for line in listing.splitlines() if line.strip()]
    if not includes:
        conanfile.output.warning(
            f"BazelToolchain could not detect builtin include directories from {driver}. "
            "System headers may be rejected by the Bazel sandbox."
        )
    return includes


def _unix_config(conanfile, settings, conf):
    """unix_cc_toolchain_config attributes for a Linux gcc or clang profile, or None."""
    compiler = settings.get_safe("compiler")
    if settings.get_safe("os") != "Linux" or compiler not in _UNIX_COMPILERS:
        return None
    executables = _compiler_executables(conf)
    c_default, cpp_default = _UNIX_COMPILERS[compiler]
    cc = _tool_path(executables.get("c") or c_default)
    cxx = _tool_path(executables.get("cpp") or cpp_default)
    if not cc or not cxx:
        conanfile.output.warning(
            "BazelToolchain could not find the compiler executable. "
            "Set tools.build:compiler_executables or make the compiler available on PATH."
        )
        return None
    view = _ProfileView(settings, conf)
    arch_flag = architecture_flag(view)
    stdlib, stdlib_define = libcxx_flags(view)
    stdcpp = stdcpp_library(view)
    sysroot = conf.get("tools.build:sysroot")
    return "unix_cc_toolchain_config", {
        "cpu": _ARCH_CONSTRAINTS[settings.get_safe("arch")],
        "compiler": compiler,
        "tool_paths": {"gcc": cc, "cpp": cxx, "ld": cxx,
                       **{tool: _binutil(cc, tool) for tool in _BINUTILS}},
        "cxx_builtin_include_directories": _builtin_includes(conanfile, cxx),
        "compile_flags": _flags(arch_flag, stdlib_define and f"-D{stdlib_define}"),
        "cxx_flags": _flags(stdlib),
        "link_flags": _flags(arch_flag, stdlib, architecture_link_flag(view)),
        # Links run through the C driver, which does not add the C++ runtime like g++ does.
        "link_libs": _flags(stdcpp and f"-l{stdcpp}", "-lm"),
        "builtin_sysroot": sysroot and _slash(sysroot),
        **_UNIX_MODE_FLAGS,
    }


def _vcvars_env(conanfile, settings, conf):
    """The environment after the same vcvarsall call VCVars writes, for this profile.

    windows_cc_toolchain_config bakes INCLUDE, LIB and PATH into each action, so an activated
    prompt does not reach cl.exe. The values have to be captured here.
    """
    if os.name != "nt":
        return {}
    try:
        call = _vcvars_call(_ProfileView(settings, conf, conanfile.settings_build))
        output = check_output_runner(f"{call[0]} > nul && set") if call else ""
    except ConanException:
        return {}
    pairs = (line.split("=", 1) for line in output.splitlines() if "=" in line)
    return {key.upper(): value for key, value in pairs}


def _msvc_config(conanfile, settings, conf):
    """windows_cc_toolchain_config attributes for a Windows msvc profile, or None.

    The cpu stays x64_windows so the config keeps the cl.exe actions. Other architectures use
    their own cl.exe, their vcvars environment and /MACHINE.
    """
    if settings.get_safe("os") != "Windows" or settings.get_safe("compiler") != "msvc":
        return None
    arch = settings.get_safe("arch")
    machine = _MSVC_MACHINE.get(arch)
    if not machine:
        conanfile.output.warning(f"BazelToolchain skips the MSVC compiler for arch={arch!r}. "
                                 f"Supported architectures are {sorted(_MSVC_MACHINE)}.")
        return None
    executables = _compiler_executables(conf)
    cl = _tool_path(executables.get("c") or executables.get("cpp") or "cl")
    if not cl:
        conanfile.output.warning("BazelToolchain could not find cl.exe. Set "
                                 "tools.build:compiler_executables or make cl available on PATH.")
        return None
    env = _vcvars_env(conanfile, settings, conf) or os.environ
    include, lib_env = env.get("INCLUDE", ""), env.get("LIB", "")
    if not include or not lib_env:
        conanfile.output.warning(f"BazelToolchain MSVC toolchain has no INCLUDE or LIB for "
                                 f"arch={arch!r}. Install the Visual Studio tools for that "
                                 "architecture.")
    folder = posixpath.dirname(cl)
    link, lib = posixpath.join(folder, "link.exe"), posixpath.join(folder, "lib.exe")
    assembler = _MSVC_ASSEMBLER.get(machine)
    machine_flags = [f"/MACHINE:{machine}"]
    return "windows_cc_toolchain_config", {
        "cpu": "x64_windows",
        "compiler": "msvc-cl",
        "tool_paths": {"gcc": cl, "cpp": cl, "ld": link, "ar": lib},
        "cxx_builtin_include_directories": [_slash(p) for p in include.split(";") if p.strip()],
        "msvc_cl_path": cl,
        "msvc_link_path": link,
        "msvc_lib_path": lib,
        "msvc_ml_path": assembler and posixpath.join(folder, assembler),
        "msvc_env_include": include,
        "msvc_env_lib": lib_env,
        "msvc_env_path": env.get("PATH"),
        "msvc_env_tmp": env.get("TMP") or env.get("TEMP"),
        "archiver_flags": machine_flags,
        "default_link_flags": machine_flags,
    }


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

_BUILD_TEMPLATE = _env.from_string(textwrap.dedent("""\
    {% for rule in toolchains|map(attribute="rule")|unique %}
    load("{{ config_rules[rule] }}", {{ rule }} = "cc_toolchain_config")
    {% endfor %}
    {% if toolchains %}
    load("@rules_cc//cc/toolchains:cc_toolchain.bzl", "cc_toolchain")

    {% endif %}
    package(default_visibility = ["//visibility:public"])
    {% for name, constraints in platforms.items() %}

    platform(
        name = "{{ name }}",
        constraint_values = {{ constraints|starlark }},
    )
    {% endfor %}
    {% if toolchains %}

    filegroup(name = "empty")
    {% endif %}
    {% for tc in toolchains %}

    {{ tc.rule }}(
        name = "{{ tc.name }}_config",
        toolchain_identifier = "conan_{{ tc.name }}",
        host_system_name = "local",
        target_system_name = "local",
        target_libc = "unknown",
        abi_version = "unknown",
        abi_libc_version = "unknown",
        {% for key, value in tc.attrs.items() if value %}
        {{ key }} = {{ value|starlark }},
        {% endfor %}
    )

    cc_toolchain(
        name = "{{ tc.name }}_cc",
        toolchain_identifier = "conan_{{ tc.name }}",
        toolchain_config = ":{{ tc.name }}_config",
        all_files = ":empty",
        compiler_files = ":empty",
        dwp_files = ":empty",
        linker_files = ":empty",
        objcopy_files = ":empty",
        strip_files = ":empty",
        supports_param_files = 0,
    )

    toolchain(
        name = "cc_for_{{ tc.name }}",
        toolchain = ":{{ tc.name }}_cc",
        toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
        exec_compatible_with = {{ tc.exec_constraints|starlark }},
        target_compatible_with = {{ tc.target_constraints|starlark }},
    )
    {% endfor %}
    """))

_MODULE_TEMPLATE = _env.from_string(textwrap.dedent("""\
    # Generated by BazelToolchain. Include in your MODULE.bazel file with:
    # include("{{ include }}")
    {% if toolchains %}
    # Requires bazel_dep(name = "rules_cc") in your MODULE.bazel. BazelDeps already adds it.
    {% endif %}

    bazel_dep(name = "platforms", version = "{{ platforms_version }}")
    {% if toolchains %}
    register_toolchains(
    {% for tc in toolchains %}
        "{{ package }}:cc_for_{{ tc.name }}",
    {% endfor %}
    )
    {% endif %}
    """))


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

    def _generators_folder(self):
        """The generators folder relative to the workspace root, "" for the root itself."""
        folder = posixpath.normpath(_slash(self._conanfile.folders.generators or "."))
        return "" if folder == "." else folder

    def _toolchains(self, exec_constraints, target_constraints):
        """One toolchain for the host profile. A cross build adds one for the build profile."""
        conanfile = self._conanfile
        profiles = [("target", conanfile.settings, conanfile.conf, target_constraints)]
        if exec_constraints != target_constraints:
            profiles.append(("host", conanfile.settings_build, conanfile.conf_build,
                             exec_constraints))
        toolchains = []
        for name, settings, conf, constraints in profiles:
            config = (_unix_config(conanfile, settings, conf)
                      or _msvc_config(conanfile, settings, conf))
            if config:
                rule, attrs = config
                toolchains.append({"name": name, "rule": rule, "attrs": attrs,
                                   "exec_constraints": exec_constraints,
                                   "target_constraints": constraints})
        return toolchains

    def _write_platforms(self, exec_constraints, target_constraints):
        """Writes the platforms, the toolchains and the module snippet. Returns the package."""
        folder = self._generators_folder()
        package = f"//{posixpath.join(folder, _TOOLCHAIN_PACKAGE)}"
        toolchains = self._toolchains(exec_constraints, target_constraints)
        build = _BUILD_TEMPLATE.render(
            config_rules=_CONFIG_RULES, toolchains=toolchains,
            platforms={"host": exec_constraints, "target": target_constraints},
        )
        module = _MODULE_TEMPLATE.render(
            include=f"//{folder}:{_MODULE_FILENAME}", package=package, toolchains=toolchains,
            platforms_version=_PLATFORMS_VERSION,
        )
        save(self._conanfile, os.path.join(_TOOLCHAIN_PACKAGE, "BUILD.bazel"), build)
        save(self._conanfile, _MODULE_FILENAME, module)
        save(self._conanfile, "BUILD.bazel", "# This is an empty BUILD file.")
        return package

    def generate(self):
        """
        Creates a ``conan_bzl.rc`` file with one ``conan-config`` configuration. Pass
        ``--config=conan-config`` to use it. The build type is ``--compilation_mode`` inside
        that config. A later install overwrites the file.

        Also writes host and target ``platform()`` rules and a ``conan_toolchain.MODULE.bazel``
        snippet when both profiles define ``os`` and ``arch``. For gcc and clang on Linux, and for
        msvc on Windows, it writes the ``cc_toolchain`` that Bazel uses for that profile. An msvc
        cross build writes one toolchain per profile, with that profile's vcvars environment.
        Those toolchains load ``rules_cc``, so the ``MODULE.bazel`` needs
        ``bazel_dep(name = "rules_cc")``. The BazelDeps module snippet already declares it.
        """
        check_duplicated_generator(self, self._conanfile)
        config = self.bazelrc_config
        lines = [Template(self.bazelrc_template).render(self._context()).rstrip("\n")]
        if is_msvc_static_runtime(self._conanfile):
            # The rules_cc windows config links the dynamic runtime unless this feature is set.
            lines.append(f"build:{config} --features=static_link_msvcrt")
        exec_constraints = _platform_constraints(self._conanfile.settings_build)
        target_constraints = _platform_constraints(self._conanfile.settings)
        if exec_constraints and target_constraints:
            package = self._write_platforms(exec_constraints, target_constraints)
            lines.append(f"build:{config} --platforms={package}:target")
            lines.append(f"build:{config} --host_platform={package}:host")
        save(self._conanfile, self.bazelrc_name, "\n".join(lines) + "\n")
        self._conanfile.output.info(f"BazelToolchain generated: {self.bazelrc_name}")
        if is_consumer(self._conanfile):
            rc_path = posixpath.join(self._generators_folder(), self.bazelrc_name)
            msg = textwrap.dedent(f"""\
                BazelToolchain: Config '{config}' added to {rc_path}.
                    bazel --bazelrc={rc_path} build --config={config} //...
                    Or add to .bazelrc: try-import %workspace%/{rc_path}
                    bazel build --config={config} //...""")
            self._conanfile.output.info(msg, fg=Color.CYAN)
