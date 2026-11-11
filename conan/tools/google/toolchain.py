"""
PROPOSAL: BazelToolchain based on Bazel platforms + toolchain resolution.

Instead of filling a bazelrc file with loose CLI flags (``--cpu``, ``--crosstool_top``,
``--copt``...), this generator models the Conan configuration the way Bazel >= 7 expects:

* ``platform()`` targets for the host (``settings``) and build (``settings_build``) machines,
  built from ``@platforms//os`` and ``@platforms//cpu`` constraints.
* A real C/C++ toolchain: a ``cc_toolchain_config`` rule (Starlark, ``cc_common``) with
  absolute ``tool_paths`` and all the Conan flags expressed as Bazel *features*, a
  ``cc_toolchain`` and a ``toolchain()`` registered for the ``@bazel_tools//tools/cpp:toolchain_type``.
* A ``conan_toolchain.MODULE.bazel`` snippet that registers the toolchain. Toolchains
  registered by the root module have priority over Bazel's auto-configured
  ``@local_config_cc``, so native builds need no extra flags at all: Bazel's auto-detected
  host platform matches the toolchain ``os``/``cpu`` constraints.
* Everything that used to be a CLI flag lives in the toolchain itself: PIC (``-fPIC`` in the
  compile flags), optimization/debug flags (Conan ``build_type`` flags) and an override of
  ``strip_debug_symbols`` so Bazel's default ``fastbuild`` mode never strips the binaries.
* A minimal ``conan_bzl.rc`` (``conan-config``), **only when cross-building**, with
  ``--platforms`` and ``--host_platform``. Bazel only admits the target platform from the
  command line/bazelrc. The ``Bazel`` helper uses it automatically if it exists.

Generated files (with ``bazel_layout``, inside ``<build>/conan``)::

    conan/
    ├── BUILD.bazel                         # empty, makes //conan a package
    ├── conan_toolchain.MODULE.bazel        # register_toolchains(...)
    ├── conan_bzl.rc                        # only if cross-building (or MSVC fallback)
    └── conan_toolchain/
        ├── BUILD.bazel                     # platforms, cc_toolchain, toolchain
        └── conan_cc_toolchain_config.bzl   # generic cc_toolchain_config rule (static)

Requirements in the consumer ``MODULE.bazel`` (Bazel >= 7.2 for ``include()``)::

    bazel_dep(name = "platforms", version = "1.1.0")
    bazel_dep(name = "rules_cc", version = "0.2.17")   # already added by BazelDeps include
    include("//conan:conan_toolchain.MODULE.bazel")

Notice that the registered toolchain is selected for any target platform with the same
``os``/``cpu`` constraints, not only for the Conan generated ones.

MSVC/clang-cl: writing a full MSVC ``cc_toolchain_config`` is out of the scope of this first
iteration. For them (or when ``generate_cc_toolchain = False``), only the platforms are
generated and Bazel keeps using its auto-configured ``@local_config_cc`` toolchain, with the
Conan flags passed as ``--copt/--cxxopt/--conlyopt/--linkopt`` in the bazelrc file (legacy
behavior). In that case, the ``conan_bzl.rc`` is generated even for native builds.

More information:
    * Platforms: https://bazel.build/extending/platforms
    * Toolchain resolution: https://bazel.build/extending/toolchains
    * C++ toolchain configuration: https://bazel.build/docs/cc-toolchain-config-reference
    * Tutorial: https://bazel.build/tutorials/ccp-toolchain-config
"""
import os
import platform
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
from conan.tools.microsoft import msvc_runtime_flag, is_msvc


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
    toolchain_config_filename = "conan_cc_toolchain_config.bzl"
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
        {% endif %}
        """)

    _build_template = textwrap.dedent("""\
        # Automatically generated by Conan BazelToolchain. Do not edit it.
        {% if generate_cc_toolchain %}
        load("@rules_cc//cc:defs.bzl", "cc_toolchain")
        load(":{{ config_filename }}", "conan_cc_toolchain_config")
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

        conan_cc_toolchain_config(
            name = "cc_toolchain_config",
            toolchain_identifier = "{{ toolchain_identifier }}",
            compiler = "{{ compiler }}",
            target_cpu = "{{ target_cpu }}",
            target_system_name = "{{ target_system_name }}",
            target_libc = "{{ target_libc }}",
            tool_paths = {{ tool_paths }},
            cxx_builtin_include_directories = {{ cxx_builtin_include_directories }},
            builtin_sysroot = "{{ builtin_sysroot }}",
            archiver = "{{ archiver }}",
            supports_dynamic_linker = {{ supports_dynamic_linker }},
            compile_flags = {{ compile_flags }},
            c_flags = {{ c_flags }},
            cxx_flags = {{ cxx_flags }},
            objc_flags = {{ objc_flags }},
            link_flags = {{ link_flags }},
            exe_link_flags = {{ exe_link_flags }},
            shared_link_flags = {{ shared_link_flags }},
            link_libs = {{ link_libs }},
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

    # Static file: the rule is generic, every Conan value is passed as attribute from BUILD.bazel
    _toolchain_config_content = textwrap.dedent("""\
        # Automatically generated by Conan BazelToolchain. Do not edit it.
        # Generic cc_toolchain_config rule. All the values are injected from BUILD.bazel
        load("@rules_cc//cc:action_names.bzl", "ACTION_NAMES")
        load(
            "@rules_cc//cc:cc_toolchain_config_lib.bzl",
            "feature",
            "flag_group",
            "flag_set",
            "tool_path",
            "variable_with_value",
        )
        load("@rules_cc//cc/common:cc_common.bzl", "cc_common")
        load("@rules_cc//cc/toolchains:cc_toolchain_config_info.bzl", "CcToolchainConfigInfo")

        _C_COMPILE = [ACTION_NAMES.c_compile]
        _CXX_COMPILE = [
            ACTION_NAMES.cpp_compile,
            ACTION_NAMES.cpp_header_parsing,
            ACTION_NAMES.cpp_module_compile,
            ACTION_NAMES.cpp_module_codegen,
            ACTION_NAMES.linkstamp_compile,
            ACTION_NAMES.lto_backend,
            ACTION_NAMES.clif_match,
        ]
        _OBJC_COMPILE = [ACTION_NAMES.objc_compile, ACTION_NAMES.objcpp_compile]
        _ASM = [ACTION_NAMES.assemble, ACTION_NAMES.preprocess_assemble]
        _ALL_COMPILE = _C_COMPILE + _CXX_COMPILE + _OBJC_COMPILE + _ASM
        _LINK_EXE = [ACTION_NAMES.cpp_link_executable]
        _LINK_SHARED = [
            ACTION_NAMES.cpp_link_dynamic_library,
            ACTION_NAMES.cpp_link_nodeps_dynamic_library,
        ]
        _ALL_LINK = _LINK_EXE + _LINK_SHARED

        def _flags_feature(name, actions, flags):
            if not flags:
                return None
            return feature(
                name = name,
                enabled = True,
                flag_sets = [flag_set(actions = actions, flag_groups = [flag_group(flags = flags)])],
            )

        def _libtool_archiver_feature():
            # Apple "ar" does not understand Bazel's default "rcsD", use "libtool -static" instead
            return feature(
                name = "archiver_flags",
                flag_sets = [
                    flag_set(
                        actions = [ACTION_NAMES.cpp_link_static_library],
                        flag_groups = [
                            flag_group(flags = ["-static", "-no_warning_for_no_symbols"]),
                            flag_group(
                                flags = ["-o", "%{output_execpath}"],
                                expand_if_available = "output_execpath",
                            ),
                        ],
                    ),
                    flag_set(
                        actions = [ACTION_NAMES.cpp_link_static_library],
                        flag_groups = [
                            flag_group(
                                iterate_over = "libraries_to_link",
                                expand_if_available = "libraries_to_link",
                                flag_groups = [
                                    flag_group(
                                        flags = ["%{libraries_to_link.name}"],
                                        expand_if_equal = variable_with_value(
                                            name = "libraries_to_link.type",
                                            value = "object_file",
                                        ),
                                    ),
                                    flag_group(
                                        flags = ["%{libraries_to_link.object_files}"],
                                        iterate_over = "libraries_to_link.object_files",
                                        expand_if_equal = variable_with_value(
                                            name = "libraries_to_link.type",
                                            value = "object_file_group",
                                        ),
                                    ),
                                ],
                            ),
                        ],
                    ),
                ],
            )

        def _impl(ctx):
            attr = ctx.attr
            features = [
                feature(name = "supports_pic", enabled = True),
                feature(name = "supports_dynamic_linker", enabled = attr.supports_dynamic_linker),
                # Overrides the legacy feature (-Wl,-S) applied with the default "fastbuild"
                # compilation mode. Conan build_type flags decide about debug information.
                feature(name = "strip_debug_symbols"),
            ]
            if attr.archiver == "libtool":
                features.append(_libtool_archiver_feature())
            features += [f for f in [
                _flags_feature("conan_compile_flags", _ALL_COMPILE, attr.compile_flags),
                _flags_feature("conan_c_flags", _C_COMPILE, attr.c_flags),
                _flags_feature("conan_cxx_flags", _CXX_COMPILE, attr.cxx_flags),
                _flags_feature("conan_objc_flags", _OBJC_COMPILE, attr.objc_flags),
                _flags_feature("conan_link_flags", _ALL_LINK, attr.link_flags),
                _flags_feature("conan_exe_link_flags", _LINK_EXE, attr.exe_link_flags),
                _flags_feature("conan_shared_link_flags", _LINK_SHARED, attr.shared_link_flags),
                _flags_feature("conan_link_libs", _ALL_LINK, attr.link_libs),
            ] if f]

            return cc_common.create_cc_toolchain_config_info(
                ctx = ctx,
                toolchain_identifier = attr.toolchain_identifier,
                compiler = attr.compiler,
                target_cpu = attr.target_cpu,
                target_system_name = attr.target_system_name,
                target_libc = attr.target_libc,
                abi_version = "local",
                abi_libc_version = "local",
                host_system_name = "local",
                builtin_sysroot = attr.builtin_sysroot or None,
                cxx_builtin_include_directories = attr.cxx_builtin_include_directories,
                tool_paths = [tool_path(name = k, path = v) for k, v in attr.tool_paths.items()],
                features = features,
            )

        conan_cc_toolchain_config = rule(
            implementation = _impl,
            attrs = {
                "toolchain_identifier": attr.string(mandatory = True),
                "compiler": attr.string(mandatory = True),
                "target_cpu": attr.string(mandatory = True),
                "target_system_name": attr.string(mandatory = True),
                "target_libc": attr.string(default = "unknown"),
                "tool_paths": attr.string_dict(mandatory = True),
                "cxx_builtin_include_directories": attr.string_list(),
                "builtin_sysroot": attr.string(),
                "archiver": attr.string(default = "ar", values = ["ar", "libtool"]),
                "supports_dynamic_linker": attr.bool(default = True),
                "compile_flags": attr.string_list(),
                "c_flags": attr.string_list(),
                "cxx_flags": attr.string_list(),
                "objc_flags": attr.string_list(),
                "link_flags": attr.string_list(),
                "exe_link_flags": attr.string_list(),
                "shared_link_flags": attr.string_list(),
                "link_libs": attr.string_list(),
            },
            provides = [CcToolchainConfigInfo],
        )
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
        #: Disable asserts (``-DNDEBUG``) if not Debug
        self.ndebug = build_type not in (None, "Debug")
        #: C++ standard flag
        self.cppstd = cppstd_flag(conanfile)
        #: C standard flag
        self.cstd = cstd_flag(conanfile)
        self.libcxx, self.gcc_cxx11_abi = libcxx_flags(conanfile)
        #: MSVC runtime flag (only used if not ``generate_cc_toolchain``)
        self.msvc_runtime_flag = f"-{msvc_runtime_flag(conanfile)}" if msvc_like and \
            msvc_runtime_flag(conanfile) else None
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
        ndk_bin = os.path.join(ndk_path, "toolchains", "llvm", "prebuilt",
                               f"{host_tag}-x86_64", "bin")
        api_level = self._conanfile.settings.get_safe("os.api_level")
        target = {"armv7": "armv7a-linux-androideabi",
                  "armv8": "aarch64-linux-android",
                  "x86": "i686-linux-android",
                  "x86_64": "x86_64-linux-android"}.get(self._arch)
        ext = ".cmd" if os_build == "Windows" else ""
        self.c = os.path.join(ndk_bin, f"{target}{api_level}-clang{ext}")
        self.cpp = os.path.join(ndk_bin, f"{target}{api_level}-clang++{ext}")
        self.ar = os.path.join(ndk_bin, "llvm-ar")
        self.strip = os.path.join(ndk_bin, "llvm-strip")
        self.nm = os.path.join(ndk_bin, "llvm-nm")
        self.objdump = os.path.join(ndk_bin, "llvm-objdump")
        self.objcopy = os.path.join(ndk_bin, "llvm-objcopy")
        self.cxx_builtin_include_directories.append(ndk_path)

    # -------------------------------------------------------------------------------------------
    # Context
    # -------------------------------------------------------------------------------------------
    @staticmethod
    def _filter(v):
        return [f for f in v if f]

    @staticmethod
    def _to_abs_tool(tool):
        """
        Bazel resolves relative ``tool_paths`` against the toolchain package, so every tool
        has to be an absolute path. Unknown tools point to a failing binary, as Bazel suggests.
        """
        if isinstance(tool, list) or (tool and len(tool.split()) > 1):
            raise ConanException(f"BazelToolchain: '{tool}' is not a single executable. Bazel "
                                 "tool_paths do not admit wrappers/arguments (e.g., ccache), "
                                 "use a wrapper script instead.")
        if tool and os.path.isabs(tool):
            return tool.replace("\\", "/")
        found = shutil.which(tool) if tool else None
        if found:
            return found.replace("\\", "/")
        return "C:/Windows/System32/false.exe" if platform.system() == "Windows" else "/bin/false"

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
            prefix = os.path.dirname(os.path.dirname(os.path.realpath(tool)))
            if prefix not in ("/", "") and not tool.endswith("false"):
                dirs.append(prefix.replace("\\", "/"))
        if self._is_apple_system:
            # Same defaults as Bazel's auto-configured Apple toolchain
            dirs += ["/Applications/", "/Library/"]
            dirs += [f for f in self.apple_isysroot_flag if os.path.isabs(f)]
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
        if self.msvc_runtime_flag:
            compile_flags.append(self.msvc_runtime_flag)
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
        """ Flags passed via bazelrc when Bazel's auto-configured toolchain is used """
        if self.generate_cc_toolchain:
            return []
        flags = self._get_flags()
        compilation_mode = {"Release": "opt", "Debug": "dbg", "RelWithDebInfo": "opt",
                            "MinSizeRel": "opt"}.get(self._conanfile.settings.get_safe("build_type"))
        ret = [f"--compilation_mode={compilation_mode}"] if compilation_mode else []
        ret += [f"--copt={f}" for f in flags["compile_flags"]]
        ret += [f"--conlyopt={f}" for f in flags["c_flags"]]
        ret += [f"--cxxopt={f}" for f in flags["cxx_flags"]]
        ret += [f"--linkopt={f}" for f in flags["link_flags"] + flags["exe_link_flags"] +
                flags["shared_link_flags"]]
        return ret

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
            "config_filename": self.toolchain_config_filename,
            "host_constraints": to_starlark(self.host_constraints),
            "build_constraints": to_starlark(self.build_constraints),
            "exec_compatible_with": to_starlark(self.build_constraints),
        }
        if self.generate_cc_toolchain:
            tool_paths = self._get_tool_paths()
            flags = self._get_flags()
            ctx.update({
                "toolchain_identifier": "_".join(str(v) for v in (
                    "conan", self._os, self._arch, self._compiler,
                    self._conanfile.settings.get_safe("compiler.version")) if v).lower(),
                "compiler": to_bazel_compiler(self._compiler),
                "target_cpu": (to_bazel_cpu_constraint(self._arch) or
                               f":{self._arch}").split(":")[-1],
                "target_system_name": str(self._os).lower(),
                "target_libc": "macosx" if self._os == "Macos" else "unknown",
                "tool_paths": to_starlark(tool_paths),
                "cxx_builtin_include_directories": to_starlark(
                    self._get_builtin_include_directories(tool_paths)),
                "builtin_sysroot": (self.sysroot or "").replace("\\", "/"),
                "archiver": "libtool" if os.path.basename(tool_paths["ar"]) == "libtool" else "ar",
                "supports_dynamic_linker": to_starlark(self._os not in ("baremetal", "Arduino")),
                "link_libs": to_starlark(self._link_libs),
            })
            ctx.update({k: to_starlark(v) for k, v in flags.items()})
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
        if self.generate_cc_toolchain:
            save(os.path.join(folder, self.toolchain_config_filename),
                 self._toolchain_config_content)
        # The generators folder has to be a Bazel package to include() the module snippet.
        # BazelDeps creates the same empty file, do not overwrite it.
        if not os.path.exists("BUILD.bazel"):
            save("BUILD.bazel", "# This is an empty BUILD file.")
        module_label = f"{self._generators_package}:{self.module_filename}"
        save(self.module_filename, self._render(self._module_template, {
            "module_label": module_label,
            "package": package,
            "generate_cc_toolchain": self.generate_cc_toolchain,
        }))

        rc_flags = self._rc_flags
        if self._is_cross_building or rc_flags:
            save(self.bazelrc_name, self._render(self._bazelrc_template, {
                "package": package,
                "cross_building": self._is_cross_building,
                "rc_flags": rc_flags,
            }))
            rc_msg = f" and {self.bazelrc_name} (--config={self.bazelrc_config})"
        else:
            # A stale one (e.g., previous cross-build install) would be used by the Bazel helper
            if os.path.exists(self.bazelrc_name):
                os.remove(self.bazelrc_name)
            rc_msg = ""
        self._conanfile.output.info(f"BazelToolchain generated: {module_label}{rc_msg}")
