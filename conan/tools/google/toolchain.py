"""
Creates a ``conan_bzl.rc`` file which defines a conan-config configuration with all the
attributes defined by the consumer, plus host and target platforms. Bazel keeps the compiler
it detected. A cross-build ``cc_toolchain`` can be added per compiler through
``_CROSS_TOOLCHAINS``.

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
import os
import textwrap

from jinja2 import Template

from conan.errors import ConanException
from conan.internal import check_duplicated_generator
from conan.internal.internal_tools import raise_on_universal_arch
from conan.tools.build.cross_building import cross_building
from conan.tools.build.flags import cppstd_flag
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
_TOOLCHAIN_PACKAGE = "conan_toolchain"
_MODULE_FILENAME = "conan_toolchain.MODULE.bazel"
# settings.compiler -> callable(conanfile, exec_constraints, target_constraints, package).
# The callable returns (build_rules, module_lines) for a cross build. gcc, clang and msvc
# each get one entry. None are registered yet, so Bazel keeps the toolchain it detected.
_CROSS_TOOLCHAINS = {}


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


def _cross_toolchain(conanfile, exec_constraints, target_constraints, package):
    if not cross_building(conanfile):
        return None
    builder = _CROSS_TOOLCHAINS.get(conanfile.settings.get_safe("compiler"))
    if builder is None:
        return None
    return builder(conanfile, exec_constraints, target_constraints, package)


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

    def _write_platforms(self, exec_constraints, target_constraints):
        parts = _generators_parts(self._conanfile)
        folder_name = _TOOLCHAIN_PACKAGE
        package = "//" + "/".join(parts + [folder_name])
        build = "\n\n".join((
            _platform_rule("host", exec_constraints),
            _platform_rule("target", target_constraints),
        )) + "\n"
        deps = [f'bazel_dep(name = "platforms", version = "{_PLATFORMS_VERSION}")']
        extra = _cross_toolchain(self._conanfile, exec_constraints, target_constraints, package)
        if extra:
            rules, module_lines = extra
            build += "\n" + rules
            deps.extend(module_lines)
        save(self._conanfile, os.path.join(folder_name, "BUILD.bazel"), build)
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
        Creates a ``conan_bzl.rc`` file with some bazel-build configuration. This last mentioned
        is put as ``conan-config``.

        Also writes host and target ``platform()`` rules and a ``conan_toolchain.MODULE.bazel``
        snippet when both profiles define ``os`` and ``arch``. Bazel keeps the compiler it detected.
        """
        check_duplicated_generator(self, self._conanfile)
        exec_constraints = self._constraints(self._conanfile.settings_build)
        target_constraints = self._constraints(self._conanfile.settings)
        platform_lines = []
        if exec_constraints and target_constraints:
            platform_lines = self._write_platforms(exec_constraints, target_constraints)
        save(self._conanfile, BazelToolchain.bazelrc_name, self._rc_content(platform_lines))
