"""
PROPOSAL: BazelToolchain based on Bazel platforms + toolchain resolution.

Instead of filling a bazelrc file with loose CLI flags (``--cpu``, ``--crosstool_top``,
``--copt``...), this generator models the Conan configuration the way Bazel >= 7 expects:

* ``platform()`` targets for the host (``settings``) and build (``settings_build``) machines,
  built from ``@platforms//os`` and ``@platforms//cpu`` constraints.
* A real C/C++ toolchain: the official rules_cc Unix ``cc_toolchain_config`` rule (the same one
  used by Bazel's auto-configured ``@local_config_cc``) with absolute ``tool_paths`` and all the
  Conan flags, a ``cc_toolchain`` and a ``toolchain()`` registered for the
  ``@bazel_tools//tools/cpp:toolchain_type``. Flags without an equivalent attribute (exe/shared
  link flags, ObjC flags) are injected as rules_cc rule-based ``cc_feature``.
* A ``conan_toolchain.MODULE.bazel`` snippet that registers the toolchain. Toolchains
  registered by the root module have priority over Bazel's auto-configured
  ``@local_config_cc``, so native builds need no extra flags at all: Bazel's auto-detected
  host platform matches the toolchain ``os``/``cpu`` constraints.
* Everything that used to be a CLI flag lives in the toolchain itself: PIC (``-fPIC`` in the
  compile flags) and optimization/debug flags (Conan ``build_type`` flags). Notice that Bazel
  default ``fastbuild`` mode strips the debug symbols (``--strip=sometimes``), use
  ``-c dbg`` or ``--strip=never`` if you need them.
* A minimal ``conan_bzl.rc`` (``conan-config``), **only when cross-building**, with
  ``--platforms`` and ``--host_platform``. Bazel only admits the target platform from the
  command line/bazelrc. The ``Bazel`` helper uses it automatically if it exists.

Generated files (with ``bazel_layout``, inside ``<build>/conan``)::

    conan/
    ├── BUILD.bazel                         # empty, makes //conan a package
    ├── conan_toolchain.MODULE.bazel        # register_toolchains(...)
    ├── conan_bzl.rc                        # only if cross-building (or MSVC fallback)
    └── conan_toolchain/
        └── BUILD.bazel                     # platforms, cc_toolchain_config, toolchain

Requirements in the consumer ``MODULE.bazel`` (Bazel >= 7.2 for ``include()``)::

    bazel_dep(name = "platforms", version = "1.1.0")
    bazel_dep(name = "rules_cc", version = "0.2.17")   # >= 0.2.17 (cc_toolchain_config)
    include("//conan:conan_toolchain.MODULE.bazel")

Notice that the registered toolchain is selected for any target platform with the same
``os``/``cpu`` constraints, not only for the Conan generated ones.

MSVC/clang-cl: the rules_cc Windows ``cc_toolchain_config`` needs the whole ``vcvars``
environment (``PATH``, ``INCLUDE``, ``LIB``), so for them (or when
``generate_cc_toolchain = False``), only the platforms are generated and Bazel keeps using its
auto-configured ``@local_config_cc`` toolchain. Conan points it to the right installation
(``--repo_env=BAZEL_VC/BAZEL_VC_FULL_VERSION/BAZEL_WINSDK_FULL_VERSION/BAZEL_LLVM``), selects the
runtime with the ``static_link_msvcrt`` feature, registers the clang-cl toolchain if needed, and
passes the Conan flags as ``--copt/--cxxopt/--conlyopt/--linkopt`` in the bazelrc file. In that
case, the ``conan_bzl.rc`` is generated even for native builds.

More information:
    * Platforms: https://bazel.build/extending/platforms
    * Toolchain resolution: https://bazel.build/extending/toolchains
    * C++ toolchain configuration: https://bazel.build/docs/cc-toolchain-config-reference
    * Tutorial: https://bazel.build/tutorials/ccp-toolchain-config
"""
import ntpath
import os
import posixpath
import shutil
import textwrap

from jinja2 import Template, StrictUndefined

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.internal_tools import raise_on_universal_arch
from conan.internal.model.pkg_type import PackageType
from conan.internal.util.files import save
from conan.tools.apple.apple import is_apple_os, apple_min_version_flag, resolve_apple_flags, \
    apple_extra_flags
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import architecture_flag, architecture_link_flag, threads_flags, \
    libcxx_flags, cppstd_flag, cstd_flag, build_type_flags
from conan.tools.env import VirtualBuildEnv
from conan.tools.google.helpers import to_bazel_os_constraint, to_bazel_cpu_constraint, \
    to_bazel_compiler, to_starlark
from conan.internal.api.detect.detect_vs import vs_installation_path
from conan.tools.microsoft import msvc_runtime_flag, is_msvc
from conan.tools.microsoft.visual import _vcvars_versions


def _bazelrc_quote(flag):
    """
    Bazel splits every bazelrc line into tokens like a shell does, so a flag with spaces (e.g.,
    ``--repo_env=BAZEL_VC=C:/Program Files/Microsoft Visual Studio/2022/VC``) has to be quoted
    """
    if not any(c.isspace() or c in "\"'\\" for c in flag):
        return flag
    escaped = flag.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


class BazelToolchain:
    """
    BazelToolchain generator (platforms + C/C++ toolchain)
    """
    #: Name of the bazelrc file. Kept for compatibility with the ``Bazel`` build helper.
    bazelrc_name = "conan_bzl.rc"
    #: Name of the bazelrc configuration. Kept for compatibility with the ``Bazel`` build helper.
    bazelrc_config = "conan-config"
    #: Bazel package (sub-folder of the generators folder) where the toolchain is generated
    toolchain_folder = "conan_toolchain"
    #: MODULE.bazel snippet to be included by the consumer's MODULE.bazel
    module_filename = "conan_toolchain.MODULE.bazel"

    _bazelrc_template = textwrap.dedent("""\
        # Automatic bazelrc file created by Conan
        {% if cross_building %}
        build:conan-config --platforms={{ package }}:host_platform
        build:conan-config --host_platform={{ package }}:build_platform
        {% endif %}
        {% for flag in rc_flags %}
        build:conan-config {{ flag }}
        {% endfor %}
        """)

    _module_template = textwrap.dedent("""\
        # Automatically generated by Conan BazelToolchain. Include it in your MODULE.bazel:
        # include("{{ module_label }}")
        {% if generate_cc_toolchain %}
        register_toolchains("{{ package }}:cc_toolchain")
        {% elif clang_cl_toolchain %}
        conan_cc_configure = use_extension("@rules_cc//cc:extensions.bzl", "cc_configure_extension")
        use_repo(conan_cc_configure, "local_config_cc")
        register_toolchains("@local_config_cc//:{{ clang_cl_toolchain }}")
        {% endif %}
        """)

    _build_template = textwrap.dedent("""\
        # Automatically generated by Conan BazelToolchain. Do not edit it.
        {% if generate_cc_toolchain %}
        load("@rules_cc//cc:defs.bzl", "cc_toolchain")
        load("@rules_cc//cc/private/toolchain:unix_cc_toolchain_config.bzl", "cc_toolchain_config")
        {% if extra_features %}
        load("@rules_cc//cc/toolchains:args.bzl", "cc_args")
        load("@rules_cc//cc/toolchains:feature.bzl", "cc_feature")
        {% endif %}
        {% endif %}

        package(default_visibility = ["//visibility:public"])

        # Host machine: Conan "settings" (where the binaries will run)
        platform(
            name = "host_platform",
            constraint_values = {{ host_constraints }},
        )

        # Build machine: Conan "settings_build" (where the build tools run)
        platform(
            name = "build_platform",
            constraint_values = {{ build_constraints }},
        )
        {% if generate_cc_toolchain %}

        filegroup(name = "empty")
        {% for name, feature in extra_features.items() %}

        cc_args(
            name = "{{ name }}_args",
            actions = {{ feature.actions }},
            args = {{ feature.flags }},
        )

        cc_feature(
            name = "{{ name }}",
            feature_name = "{{ name }}",
            args = [":{{ name }}_args"],
        )
        {% endfor %}

        # Same rule used by the Bazel auto-configured toolchain (@local_config_cc)
        cc_toolchain_config(
            name = "cc_toolchain_config",
            toolchain_identifier = "{{ toolchain_identifier }}",
            compiler = "{{ compiler }}",
            cpu = "{{ target_cpu }}",
            host_system_name = "local",
            target_system_name = "{{ target_system_name }}",
            target_libc = "{{ target_libc }}",
            abi_version = "local",
            abi_libc_version = "local",
            tool_paths = {{ tool_paths }},
            cxx_builtin_include_directories = {{ cxx_builtin_include_directories }},
            builtin_sysroot = "{{ builtin_sysroot }}",
            compile_flags = {{ compile_flags }},
            conly_flags = {{ c_flags }},
            cxx_flags = {{ cxx_flags }},
            link_flags = {{ link_flags }},
            link_libs = {{ link_libs }},
            {% if extra_features %}
            extra_enabled_features = {{ extra_features_labels }},
            {% endif %}
        )

        cc_toolchain(
            name = "conan_cc_toolchain",
            all_files = ":empty",
            ar_files = ":empty",
            as_files = ":empty",
            compiler_files = ":empty",
            dwp_files = ":empty",
            linker_files = ":empty",
            objcopy_files = ":empty",
            strip_files = ":empty",
            toolchain_config = ":cc_toolchain_config",
        )

        toolchain(
            name = "cc_toolchain",
            exec_compatible_with = {{ exec_compatible_with }},
            target_compatible_with = {{ host_constraints }},
            toolchain = ":conan_cc_toolchain",
            toolchain_type = "@bazel_tools//tools/cpp:toolchain_type",
        )
        {% endif %}
        """)

    def __init__(self, conanfile):
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        """
        raise_on_universal_arch(conanfile)
        self._conanfile = conanfile
        self._conf = conanfile.conf
        self._is_apple_system = is_apple_os(conanfile)
        self._is_cross_building = cross_building(conanfile)

        settings = conanfile.settings
        compiler = settings.get_safe("compiler")
        if compiler is None:
            raise ConanException("BazelToolchain needs 'settings.compiler', but it is not defined")
        self._compiler = compiler
        self._os = settings.get_safe("os")
        self._is_windows = self._os in ("Windows", "WindowsStore", "WindowsCE")
        self._arch = settings.get_safe("arch")

        # ---------------------------------------------------------------------------------------
        # Platforms
        # ---------------------------------------------------------------------------------------
        #: List of constraint labels of the host platform (``settings``). The private
        #: ``:conan_toolchain`` constraint is always added at generation time.
        self.host_constraints = [c for c in (to_bazel_os_constraint(self._os),
                                             to_bazel_cpu_constraint(self._arch)) if c]
        #: List of constraint labels of the build platform (``settings_build``)
        self.build_constraints = list(self.host_constraints)
        if self._is_cross_building:
            settings_build = conanfile.settings_build
            self.build_constraints = [
                c for c in (to_bazel_os_constraint(settings_build.get_safe("os")),
                            to_bazel_cpu_constraint(settings_build.get_safe("arch"))) if c]

        build_type = settings.get_safe("build_type")
        fpic = conanfile.options.get_safe("fPIC")
        shared = conanfile.package_type is PackageType.SHARED
        #: Compile everything as position independent code (``-fPIC``). Defined by the ``fPIC``
        #: option if the library is not shared (shared libraries are always PIC in Bazel).
        self.fpic = bool(fpic) if (not shared and fpic is not None) else False

        # ---------------------------------------------------------------------------------------
        # C/C++ toolchain
        # ---------------------------------------------------------------------------------------
        msvc_like = is_msvc(conanfile) or (compiler == "clang" and
                                           settings.get_safe("compiler.runtime") is not None)
        #: Generate the ``cc_toolchain`` (and register it with ``--extra_toolchains``).
        #: If ``False``, Bazel's auto-configured toolchain is used and the Conan flags are passed
        #: as ``--copt/--cxxopt/--conlyopt/--linkopt``. ``False`` by default for MSVC/clang-cl.
        self.generate_cc_toolchain = not msvc_like
        self._is_clang_cl = msvc_like and compiler == "clang"

        build_env = VirtualBuildEnv(conanfile, auto_generate=True).vars()
        compilers_by_conf = self._conf.get("tools.build:compiler_executables", default={},
                                           check_type=dict)
        default_c, default_cpp = {"gcc": ("gcc", "g++"),
                                  "apple-clang": ("clang", "clang++"),
                                  "clang": ("clang", "clang++")}.get(compiler, ("cc", "c++"))
        # Bazel links with the "gcc" tool (the C driver), as its own autoconfiguration does,
        # so the C++ runtime is added explicitly in ``link_libs``
        #: C compiler. Used by Bazel for every compile (C, C++, asm) and link action.
        self.c = compilers_by_conf.get("c") or build_env.get("CC") or default_c
        #: C++ compiler. Only used to locate the toolchain installation directories.
        self.cpp = compilers_by_conf.get("cpp") or build_env.get("CXX") or default_cpp
        #: Archiver. ``libtool`` in Apple systems, ``ar`` otherwise.
        self.ar = build_env.get("AR") or ("libtool" if self._is_apple_system else "ar")
        #: Linker. Bazel does not call it directly (it links through the compiler driver).
        self.ld = build_env.get("LD") or "ld"
        #: Other binutils
        self.strip = build_env.get("STRIP") or "strip"
        self.nm = build_env.get("NM") or "nm"
        self.objdump = build_env.get("OBJDUMP") or "objdump"
        self.objcopy = build_env.get("OBJCOPY") or "objcopy"
        self.gcov = "gcov"
        #: Dict of extra/overridden Bazel ``tool_paths`` (``{"gcc": "/path/to/cc", ...}``)
        self.tool_paths = {}

        #: Sysroot. Defined by ``tools.build:sysroot``. Passed as ``builtin_sysroot``.
        self.sysroot = self._conf.get("tools.build:sysroot", check_type=str)
        #: List of absolute directories where the compiler looks for system headers. Bazel
        #: fails with "undeclared inclusion" errors if a used header is outside them.
        self.cxx_builtin_include_directories = []

        # Flags (same naming/semantics as MesonToolchain)
        #: List of extra ``C`` flags.
        self.extra_cflags = []
        #: List of extra ``C++`` flags.
        self.extra_cxxflags = []
        #: List of extra linker flags.
        self.extra_ldflags = []
        #: List of extra preprocessor definitions (``-D`` is added automatically).
        self.extra_defines = []
        #: Architecture flag deduced by Conan
        self.arch_flag = architecture_flag(conanfile)
        #: Architecture link flag deduced by Conan
        self.arch_link_flag = architecture_link_flag(conanfile)
        #: Threads flags deduced by Conan
        self.threads_flags = threads_flags(conanfile)
        #: Build type flags deduced by Conan (``-O3``, ``-g``...)
        self.build_type_flags = build_type_flags(conanfile)
        if msvc_like:
            # Bazel runs several cl.exe at the same time and /Zi makes them share one .pdb file
            # (error C1041). Bazel itself uses /Z7, which embeds the debug info in each object
            self.build_type_flags = ["-Z7" if f == "-Zi" else f for f in self.build_type_flags]
        #: Disable asserts (``-DNDEBUG``) if not Debug
        self.ndebug = build_type not in (None, "Debug")
        #: C++ standard flag
        self.cppstd = cppstd_flag(conanfile)
        #: C standard flag
        self.cstd = cstd_flag(conanfile)
        self.libcxx, self.gcc_cxx11_abi = libcxx_flags(conanfile)
        #: Static MSVC runtime (``static_link_msvcrt`` Bazel feature). Only used if
        #: not ``generate_cc_toolchain``
        self.msvc_static_runtime = msvc_like and "MT" in msvc_runtime_flag(conanfile)
        #: Apple flags
        self.apple_arch_flag = []
        self.apple_isysroot_flag = []
        self.apple_min_version_flag = []
        self.apple_extra_flags = apple_extra_flags(conanfile)
        self._resolve_apple_flags()
        self._resolve_android_cross_compilation()

    def _resolve_apple_flags(self):
        if not self._is_apple_system:
            return
        min_flag, arch_flag, isysroot_flag = resolve_apple_flags(
            self._conanfile, is_cross_building=self._is_cross_building)
        self.apple_arch_flag = arch_flag.split() if arch_flag else []
        self.apple_isysroot_flag = isysroot_flag.split() if isysroot_flag else []
        self.apple_min_version_flag = [apple_min_version_flag(self._conanfile)]

    def _resolve_android_cross_compilation(self):
        if not self._is_cross_building or self._os != "Android":
            return
        ndk_path = self._conf.get("tools.android:ndk_path")
        if not ndk_path:
            raise ConanException("You must provide a NDK path. Use 'tools.android:ndk_path' "
                                 "configuration field.")
        os_build = self._conanfile.settings_build.get_safe("os")
        host_tag = {"Macos": "darwin", "Windows": "windows"}.get(os_build, "linux")
        ndk_bin = self._path.join(ndk_path, "toolchains", "llvm", "prebuilt",
                                  f"{host_tag}-x86_64", "bin")
        api_level = self._conanfile.settings.get_safe("os.api_level")
        target = {"armv7": "armv7a-linux-androideabi",
                  "armv8": "aarch64-linux-android",
                  "x86": "i686-linux-android",
                  "x86_64": "x86_64-linux-android"}.get(self._arch)
        ext = ".cmd" if os_build == "Windows" else ""
        self.c = self._path.join(ndk_bin, f"{target}{api_level}-clang{ext}")
        self.cpp = self._path.join(ndk_bin, f"{target}{api_level}-clang++{ext}")
        self.ar = self._path.join(ndk_bin, "llvm-ar")
        self.strip = self._path.join(ndk_bin, "llvm-strip")
        self.nm = self._path.join(ndk_bin, "llvm-nm")
        self.objdump = self._path.join(ndk_bin, "llvm-objdump")
        self.objcopy = self._path.join(ndk_bin, "llvm-objcopy")
        self.cxx_builtin_include_directories.append(ndk_path)

    # -------------------------------------------------------------------------------------------
    # Context
    # -------------------------------------------------------------------------------------------
    @staticmethod
    def _filter(v):
        return [f for f in v if f]

    @property
    def _path(self):
        """ Path flavor of the build machine (settings_build), where the tools are located """
        os_build = self._conanfile.settings_build.get_safe("os")
        return ntpath if os_build in ("Windows", "WindowsStore", "WindowsCE") else posixpath

    def _to_abs_tool(self, tool):
        """
        Bazel resolves relative ``tool_paths`` against the toolchain package, so every tool
        has to be an absolute path. Unknown tools point to a failing binary, as Bazel suggests.
        """
        if isinstance(tool, list) or (tool and len(tool.split()) > 1):
            raise ConanException(f"BazelToolchain: '{tool}' is not a single executable. Bazel "
                                 "tool_paths do not admit wrappers/arguments (e.g., ccache), "
                                 "use a wrapper script instead.")
        if tool and self._path.isabs(tool):
            return tool.replace("\\", "/")
        found = shutil.which(tool) if tool else None
        if found:
            return found.replace("\\", "/")
        return "C:/Windows/System32/false.exe" if self._path is ntpath else "/bin/false"

    def _get_tool_paths(self):
        ret = {
            "gcc": self.c,
            "cpp": "cpp",  # C preprocessor, Bazel barely uses it
            "ar": self.ar,
            "ld": self.ld,
            "strip": self.strip,
            "nm": self.nm,
            "objdump": self.objdump,
            "objcopy": self.objcopy,
            "gcov": self.gcov,
        }
        ret.update(self.tool_paths)
        return {k: self._to_abs_tool(v) for k, v in ret.items()}

    def _get_builtin_include_directories(self, tool_paths):
        dirs = list(self.cxx_builtin_include_directories)
        # The compiler installation prefix, e.g., /usr for /usr/bin/gcc
        for tool in (tool_paths["gcc"], self._to_abs_tool(self.cpp)):
            real = os.path.realpath(tool) if os.path.exists(tool) else tool  # resolve symlinks
            prefix = self._path.dirname(self._path.dirname(real))
            if prefix not in ("/", "") and not tool.endswith("false"):
                dirs.append(prefix.replace("\\", "/"))
        if self._is_apple_system:
            # Same defaults as Bazel's auto-configured Apple toolchain
            dirs += ["/Applications/", "/Library/"]
            dirs += [f for f in self.apple_isysroot_flag if self._path.isabs(f)]
        else:
            dirs += ["/usr/include", "/usr/local/include", "/usr/lib"]
        if self.sysroot:
            dirs.append("%sysroot%")
        return list(dict.fromkeys(dirs))  # remove duplicates keeping order

    def _get_flags(self):
        conf = self._conf
        defines = conf.get("tools.build:defines", default=[], check_type=list) + self.extra_defines
        if self.ndebug:
            defines.append("NDEBUG")
        apple_flags = self.apple_isysroot_flag + self.apple_arch_flag + self.apple_min_version_flag
        compile_flags = ([self.arch_flag] + apple_flags + self.apple_extra_flags +
                         self.threads_flags + self.build_type_flags +
                         [f"-D{d}" for d in defines])
        c_flags = ([self.cstd] + conf.get("tools.build:cflags", default=[], check_type=list) +
                   self.extra_cflags)
        cxx_flags = ([self.cppstd, self.libcxx] +
                     ([f"-D{self.gcc_cxx11_abi}"] if self.gcc_cxx11_abi else []) +
                     conf.get("tools.build:cxxflags", default=[], check_type=list) +
                     self.extra_cxxflags)
        linker_scripts = conf.get("tools.build:linker_scripts", default=[], check_type=list)
        link_flags = ([self.arch_flag, self.arch_link_flag] + apple_flags +
                      self.apple_extra_flags + self.threads_flags +
                      [f"-T{s}" for s in linker_scripts] + self.extra_ldflags)
        exe_link_flags = conf.get("tools.build:exelinkflags", default=[], check_type=list)
        shared_link_flags = conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        if self.fpic and not self._is_windows:
            compile_flags.append("-fPIC")
        return {
            "compile_flags": self._filter(compile_flags),
            "c_flags": self._filter(c_flags),
            "cxx_flags": self._filter(cxx_flags),
            "objc_flags": self._filter(self._objc_flags),
            "link_flags": self._filter(link_flags),
            "exe_link_flags": self._filter(exe_link_flags),
            "shared_link_flags": self._filter(shared_link_flags),
        }

    @property
    def _objc_flags(self):
        enable_arc = self._conf.get("tools.apple:enable_arc", check_type=bool)
        return {True: ["-fobjc-arc"], False: ["-fno-objc-arc"]}.get(enable_arc, [])

    @property
    def _link_libs(self):
        """ C++ runtime, as Bazel links with the C driver """
        if self.libcxx and "libc++" in self.libcxx or self._compiler == "apple-clang":
            cpp_runtime = "-lc++"
        elif self._os == "Android":
            cpp_runtime = "-lc++"  # The NDK clang driver handles libc++ (static/shared)
        else:
            cpp_runtime = "-lstdc++"
        return [cpp_runtime, "-lm"]

    @property
    def _rc_flags(self):
        """ Flags passed via bazelrc (only used by Conan if cross-building or MSVC) """
        if self.generate_cc_toolchain:
            if self._is_apple_system and self._os != "Macos":
                # rules_cc adds -mmacosx-version-min for any "macosx" libc, it collides with
                # the Conan -mios-version-min, -mtvos-version-min, etc.
                return ["--features=-macos_minimum_os"]
            return []
        # Bazel's auto-configured toolchain (@local_config_cc)
        flags = self._get_flags()
        compilation_mode = {"Release": "opt", "Debug": "dbg", "RelWithDebInfo": "opt",
                            "MinSizeRel": "opt"}.get(self._conanfile.settings.get_safe("build_type"))
        ret = [f"--compilation_mode={compilation_mode}"] if compilation_mode else []
        # The MSVC runtime is managed by Bazel features: /MD (/MDd if "dbg") by default
        if self.msvc_static_runtime:
            ret.append("--features=static_link_msvcrt")
        ret += [f"--repo_env={k}={v}" for k, v in self._msvc_repo_env().items()]
        ret += [f"--copt={f}" for f in flags["compile_flags"]]
        ret += [f"--conlyopt={f}" for f in flags["c_flags"]]
        ret += [f"--cxxopt={f}" for f in flags["cxx_flags"]]
        ret += [f"--linkopt={f}" for f in flags["link_flags"] + flags["exe_link_flags"] +
                flags["shared_link_flags"]]
        return ret

    def _msvc_repo_env(self):
        """
        Environment variables used by the Bazel MSVC auto-configuration
        (https://bazel.build/configure/windows) to pick the Conan defined Visual Studio, MSVC
        toolset, Windows SDK and LLVM (clang-cl) installations.
        """
        ret = {}
        vs_version, vcvars_ver = _vcvars_versions(self._conanfile)
        vs_path = (self._conf.get("tools.microsoft.msbuild:installation_path") or
                   (vs_installation_path(vs_version) if vs_version else None))
        if vs_path:
            vc_path = os.path.join(vs_path, "VC")
            ret["BAZEL_VC"] = vc_path.replace("\\", "/")
            # Bazel needs the full toolset version (14.38.33130), Conan only knows the prefix
            msvc_tools = os.path.join(vc_path, "Tools", "MSVC")
            if vcvars_ver and os.path.isdir(msvc_tools):
                versions = [v for v in os.listdir(msvc_tools) if v.startswith(vcvars_ver)]
                if versions:
                    ret["BAZEL_VC_FULL_VERSION"] = max(
                        versions, key=lambda v: [int(i) for i in v.split(".") if i.isdigit()])
        winsdk_version = self._conf.get("tools.microsoft:winsdk_version")
        if winsdk_version:
            ret["BAZEL_WINSDK_FULL_VERSION"] = winsdk_version
        if self._is_clang_cl:
            clang_cl = shutil.which(self.c) if self.c else None
            if clang_cl:
                llvm_path = os.path.dirname(os.path.dirname(clang_cl))
                ret["BAZEL_LLVM"] = llvm_path.replace("\\", "/")
        return ret

    @property
    def _clang_cl_toolchain(self):
        """ Name of the @local_config_cc clang-cl toolchain. Bazel selects MSVC by default """
        if not self._is_clang_cl:
            return None
        return "cc-toolchain-arm64_windows-clang-cl" if self._arch == "armv8" else \
            "cc-toolchain-x64_windows-clang-cl"

    @property
    def _package_label(self):
        """
        Bazel package label of the generated toolchain folder, relative to the Bazel workspace
        root (the source folder), e.g., ``//conan/conan_toolchain``.
        """
        package = self._generators_package
        return f"{package}{self.toolchain_folder}" if package == "//" else \
            f"{package}/{self.toolchain_folder}"

    @property
    def _generators_package(self):
        """ Bazel package label of the generators folder, e.g., ``//conan`` """
        folder = self._conanfile.generators_folder
        rel = os.path.relpath(folder, self._conanfile.source_folder).replace("\\", "/")
        if rel.startswith(".."):
            raise ConanException(f"BazelToolchain: the generators folder '{folder}' must be "
                                 f"inside the Bazel workspace '{self._conanfile.source_folder}'. "
                                 "Use 'bazel_layout()'.")
        return "//" if rel == "." else f"//{rel}"

    @property
    def _context(self):
        if not self.host_constraints:
            raise ConanException(f"BazelToolchain: could not deduce any Bazel constraint for "
                                 f"os={self._os}, arch={self._arch}. Define "
                                 "'tc.host_constraints' in your generate() method.")
        ctx = {
            "generate_cc_toolchain": self.generate_cc_toolchain,
            "host_constraints": to_starlark(self.host_constraints),
            "build_constraints": to_starlark(self.build_constraints),
            "exec_compatible_with": to_starlark(self.build_constraints),
        }
        if self.generate_cc_toolchain:
            tool_paths = self._get_tool_paths()
            flags = self._get_flags()
            # Flags without an equivalent attribute in rules_cc "cc_toolchain_config", injected
            # as rule-based "cc_feature"s
            actions = "@rules_cc//cc/toolchains/actions"
            extra_features = {name: {"actions": to_starlark([f"{actions}:{a}" for a in acts]),
                                     "flags": to_starlark(flags[key])}
                              for name, key, acts in (
                                  ("conan_exe_link_flags", "exe_link_flags",
                                   ["cpp_link_executable"]),
                                  ("conan_shared_link_flags", "shared_link_flags",
                                   ["dynamic_library_link_actions"]),
                                  ("conan_objc_flags", "objc_flags",
                                   ["objc_compile", "objcpp_compile"]))
                              if flags[key]}
            ctx.update({
                "toolchain_identifier": "_".join(str(v) for v in (
                    "conan", self._os, self._arch, self._compiler,
                    self._conanfile.settings.get_safe("compiler.version")) if v).lower(),
                "compiler": to_bazel_compiler(self._compiler),
                "target_cpu": (to_bazel_cpu_constraint(self._arch) or
                               f":{self._arch}").split(":")[-1],
                "target_system_name": str(self._os).lower(),
                # rules_cc uses "libtool" as archiver (from tool_paths "ar") if "macosx"
                "target_libc": "macosx" if self._is_apple_system else "unknown",
                "tool_paths": to_starlark(tool_paths),
                "cxx_builtin_include_directories": to_starlark(
                    self._get_builtin_include_directories(tool_paths)),
                "builtin_sysroot": (self.sysroot or "").replace("\\", "/"),
                "compile_flags": to_starlark(flags["compile_flags"]),
                "c_flags": to_starlark(flags["c_flags"]),
                "cxx_flags": to_starlark(flags["cxx_flags"]),
                "link_flags": to_starlark(flags["link_flags"]),
                "link_libs": to_starlark(self._link_libs),
                "extra_features": extra_features,
                "extra_features_labels": to_starlark([f":{n}" for n in extra_features]),
            })
        return ctx

    def _render(self, template, context):
        return Template(template, trim_blocks=True, lstrip_blocks=True,
                        undefined=StrictUndefined).render(context)

    def generate(self):
        """
        Generates:

        * ``conan_toolchain/`` Bazel package (platforms + C/C++ toolchain).
        * ``conan_toolchain.MODULE.bazel`` to be included by your MODULE.bazel file:
          ``include("//conan:conan_toolchain.MODULE.bazel")``.
        * ``conan_bzl.rc`` only if cross-building (``--platforms`` and ``--host_platform``) or if
          the Bazel auto-configured toolchain is used (Conan flags as ``--copt``, etc.).
        """
        check_duplicated_generator(self, self._conanfile)
        package = self._package_label
        folder = self.toolchain_folder
        save(os.path.join(folder, "BUILD.bazel"), self._render(self._build_template,
                                                               self._context))
        # The generators folder has to be a Bazel package to include() the module snippet.
        # BazelDeps creates the same empty file, do not overwrite it.
        if not os.path.exists("BUILD.bazel"):
            save("BUILD.bazel", "# This is an empty BUILD file.")
        module_label = f"{self._generators_package}:{self.module_filename}"
        save(self.module_filename, self._render(self._module_template, {
            "module_label": module_label,
            "package": package,
            "generate_cc_toolchain": self.generate_cc_toolchain,
            "clang_cl_toolchain": self._clang_cl_toolchain,
        }))

        rc_flags = self._rc_flags
        if self._is_cross_building or rc_flags:
            save(self.bazelrc_name, self._render(self._bazelrc_template, {
                "package": package,
                "cross_building": self._is_cross_building,
                "rc_flags": [_bazelrc_quote(flag) for flag in rc_flags],
            }))
            rc_msg = f" and {self.bazelrc_name} (--config={self.bazelrc_config})"
        else:
            # A stale one (e.g., previous cross-build install) would be used by the Bazel helper
            if os.path.exists(self.bazelrc_name):
                os.remove(self.bazelrc_name)
            rc_msg = ""
        self._conanfile.output.info(f"BazelToolchain generated: {module_label}{rc_msg}")
