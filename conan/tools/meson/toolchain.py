import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.apple.apple import to_apple_arch, is_apple_os
from conan.tools.cross_building import cross_building, get_cross_building_settings
from conan.tools.env import VirtualBuildEnv
from conan.tools.meson.helpers import *
from conan.tools.microsoft import VCVars, msvc_runtime_flag
from conans.errors import ConanException
from conans.util.files import save


class _MesonAppleBlock(object):

    def __init__(self, conanfile, toolchain):
        self._conanfile = conanfile
        self._toolchain = toolchain

        os_ = conanfile.settings.get_safe("os")
        if not is_apple_os(os_):
            return
        # SDK path is mandatory for cross-building
        sdk_path = self._conanfile.conf["tools.meson.mesontoolchain:sdk_path"]
        if not sdk_path and self._toolchain.cross_build:
            raise ConanException("You must provide a valid SDK path for cross-compilation.")

        os_version = self._conanfile.settings.get_safe("os.version")
        os_subsystem = self._conanfile.settings.get_safe("os.subsystem")
        # It's better if os.sdk field appears in settings instead of inferring it from SDK path
        # os_sdk = os.path.basename(sdk_path).split(".")[0].lower()
        os_sdk = _MesonAppleBlock.apple_sdk_name(self._conanfile)
        arch = to_apple_arch(self._conanfile.settings.get_safe("arch"))
        # Calculating main flags
        deployment_target_flag = " " + _MesonAppleBlock.apple_min_version_flag(os_version, os_sdk,
                                                                               os_subsystem)
        sysroot_flag = " -isysroot " + sdk_path if sdk_path else ""
        arch_flag = " -arch " + arch
        # Adding all the flags needed (it does not matter if they are duplicated)
        self._toolchain.c_args = deployment_target_flag + sysroot_flag + arch_flag
        self._toolchain.c_link_args = deployment_target_flag + sysroot_flag + arch_flag
        self._toolchain.cpp_args = deployment_target_flag + sysroot_flag + arch_flag
        self._toolchain.cpp_link_args = deployment_target_flag + sysroot_flag + arch_flag

    # FIXME: 2.0: Remove this method and use the common one from conan.tools.apple.apple
    #             Depends on https://github.com/conan-io/conan/pull/10277
    @staticmethod
    def apple_min_version_flag(os_version, os_sdk, subsystem):
        """compiler flag name which controls deployment target"""
        flag = {'macosx': '-mmacosx-version-min',
                'iphoneos': '-mios-version-min',
                'iphonesimulator': '-mios-simulator-version-min',
                'watchos': '-mwatchos-version-min',
                'watchsimulator': '-mwatchos-simulator-version-min',
                'appletvos': '-mtvos-version-min',
                'appletvsimulator': '-mtvos-simulator-version-min'}.get(str(os_sdk))
        if subsystem == 'catalyst':
            # special case, despite Catalyst is macOS, it requires an iOS version argument
            flag = '-mios-version-min'
        if not flag or not os_version:
            return ''
        return "%s=%s" % (flag, os_version)

    # FIXME: 2.0: Remove this method and use the common one from conan.tools.apple.apple
    #             Depends on https://github.com/conan-io/conan/pull/10277
    @staticmethod
    def apple_sdk_name(conanfile):
        """
        Returns the 'os.sdk' (SDK name) field value. Every user should specify it because
        there could be several ones depending on the OS architecture.

        Note: In case of MacOS it'll be the same for all the architectures.
        """
        os_ = conanfile.settings.get_safe('os')
        os_sdk = conanfile.settings.get_safe('os.sdk')
        if os_sdk:
            return os_sdk
        elif os_ == "Macos":  # it has only a single value for all the architectures for now
            return "macosx"
        else:
            raise ConanException("Please, specify a suitable value for os.sdk.")


class MesonToolchain(object):
    native_filename = "conan_meson_native.ini"
    cross_filename = "conan_meson_cross.ini"

    _meson_file_template = textwrap.dedent("""
    [constants]
    preprocessor_definitions = [{% for it, value in preprocessor_definitions.items() -%}
    '-D{{ it }}="{{ value}}"'{%- if not loop.last %}, {% endif %}{% endfor %}]

    [project options]
    {% for it, value in project_options.items() -%}
    {{it}} = {{value}}
    {% endfor %}

    [binaries]
    {% if c %}c = '{{c}}'{% endif %}
    {% if cpp %}cpp = '{{cpp}}'{% endif %}
    {% if c_ld %}c_ld = '{{c_ld}}'{% endif %}
    {% if cpp_ld %}cpp_ld = '{{cpp_ld}}'{% endif %}
    {% if ar %}ar = '{{ar}}'{% endif %}
    {% if strip %}strip = '{{strip}}'{% endif %}
    {% if as %}as = '{{as}}'{% endif %}
    {% if windres %}windres = '{{windres}}'{% endif %}
    {% if pkgconfig %}pkgconfig = '{{pkgconfig}}'{% endif %}

    [built-in options]
    {% if buildtype %}buildtype = {{buildtype}}{% endif %}
    {% if debug %}debug = {{debug}}{% endif %}
    {% if default_library %}default_library = {{default_library}}{% endif %}
    {% if b_vscrt %}b_vscrt = '{{b_vscrt}}' {% endif %}
    {% if b_ndebug %}b_ndebug = {{b_ndebug}}{% endif %}
    {% if b_staticpic %}b_staticpic = {{b_staticpic}}{% endif %}
    {% if cpp_std %}cpp_std = '{{cpp_std}}' {% endif %}
    {% if backend %}backend = '{{backend}}' {% endif %}
    c_args = {{c_args}} + preprocessor_definitions
    c_link_args = {{c_link_args}}
    cpp_args = {{cpp_args}} + preprocessor_definitions
    cpp_link_args = {{cpp_link_args}}
    {% if pkg_config_path %}pkg_config_path = '{{pkg_config_path}}'{% endif %}

    {% for context, values in cross_build.items() %}
    [{{context}}_machine]
    system = '{{values["system"]}}'
    cpu_family = '{{values["cpu_family"]}}'
    cpu = '{{values["cpu"]}}'
    endian = '{{values["endian"]}}'
    {% endfor %}
    """)

    def __init__(self, conanfile, backend=None):
        self._conanfile = conanfile
        # Values are kept as Python built-ins so users can modify them more easily, and they are
        # only converted to Meson file syntax for rendering
        # priority: first user conf, then recipe, last one is default "ninja"
        backend_conf = conanfile.conf["tools.meson.mesontoolchain:backend"]
        self._backend = backend_conf or backend or 'ninja'

        build_type = self._conanfile.settings.get_safe("build_type")
        self._buildtype = {"Debug": "debug",  # Note, it is not "'debug'"
                           "Release": "release",
                           "MinSizeRel": "minsize",
                           "RelWithDebInfo": "debugoptimized"}.get(build_type, build_type)
        self._b_ndebug = "true" if self._buildtype != "debug" else "false"

        # https://mesonbuild.com/Builtin-options.html#base-options
        fpic = self._conanfile.options.get_safe("fPIC")
        shared = self._conanfile.options.get_safe("shared")
        self._b_staticpic = fpic if (shared is False and fpic is not None) else None
        # https://mesonbuild.com/Builtin-options.html#core-options
        # Do not adjust "debug" if already adjusted "buildtype"
        self._default_library = ("shared" if shared else "static") if shared is not None else None

        compiler = self._conanfile.settings.get_safe("compiler")
        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        self._cpp_std = to_cppstd_flag(compiler, cppstd)

        if compiler == "Visual Studio":
            vscrt = self._conanfile.settings.get_safe("compiler.runtime")
            self._b_vscrt = str(vscrt).lower()
        elif compiler == "msvc":
            vscrt = msvc_runtime_flag(self._conanfile)
            self._b_vscrt = str(vscrt).lower()
        else:
            self._b_vscrt = None

        self.project_options = {}
        self.preprocessor_definitions = {}
        self.pkg_config_path = self._conanfile.generators_folder

        check_using_build_profile(self._conanfile)

        self.cross_build = {}
        default_comp = ""
        default_comp_cpp = ""
        if cross_building(conanfile, skip_x64_x86=True):
            os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
            self.cross_build["build"] = to_meson_machine(os_build, arch_build)
            self.cross_build["host"] = to_meson_machine(os_host, arch_host)
            if hasattr(conanfile, 'settings_target') and conanfile.settings_target:
                settings_target = conanfile.settings_target
                os_target = settings_target.get_safe("os")
                arch_target = settings_target.get_safe("arch")
                self.cross_build["target"] = to_meson_machine(os_target, arch_target)
            if is_apple_os(os_host):  # default cross-compiler in Apple is common
                default_comp = "clang"
                default_comp_cpp = "clang++"
        else:
            if "Visual" in compiler or compiler == "msvc":
                default_comp = "cl"
                default_comp_cpp = "cl"
            elif "clang" in compiler:
                default_comp = "clang"
                default_comp_cpp = "clang++"
            elif compiler == "gcc":
                default_comp = "gcc"
                default_comp_cpp = "g++"

        # Read the VirtualBuildEnv to update the variables
        build_env = VirtualBuildEnv(self._conanfile).vars()
        self.c = build_env.get("CC") or default_comp
        self.cpp = build_env.get("CXX") or default_comp_cpp
        self.c_ld = build_env.get("CC_LD") or build_env.get("LD")
        self.cpp_ld = build_env.get("CXX_LD") or build_env.get("LD")
        self.ar = build_env.get("AR")
        self.strip = build_env.get("STRIP")
        self.as_ = build_env.get("AS")
        self.windres = build_env.get("WINDRES")
        self.pkgconfig = build_env.get("PKG_CONFIG")
        self.c_args = build_env.get("CFLAGS", "")
        self.c_link_args = build_env.get("LDFLAGS", "")
        self.cpp_args = build_env.get("CXXFLAGS", "")
        self.cpp_link_args = build_env.get("LDFLAGS", "")

        # Define all the existing blocks
        self.blocks = [
            _MesonAppleBlock(conanfile, self)
        ]

    def _context(self):
        return {
            # https://mesonbuild.com/Machine-files.html#project-specific-options
            "project_options": {k: to_meson_value(v) for k, v in self.project_options.items()},
            # https://mesonbuild.com/Builtin-options.html#directories
            # TODO : we don't manage paths like libdir here (yet?)
            # https://mesonbuild.com/Machine-files.html#binaries
            # https://mesonbuild.com/Reference-tables.html#compiler-and-linker-selection-variables
            "c": self.c,
            "cpp": self.cpp,
            "c_ld": self.c_ld,
            "cpp_ld": self.cpp_ld,
            "ar": self.ar,
            "strip": self.strip,
            "as": self.as_,
            "windres": self.windres,
            "pkgconfig": self.pkgconfig,
            # https://mesonbuild.com/Builtin-options.html#core-options
            "buildtype": to_meson_value(self._buildtype),
            "default_library": to_meson_value(self._default_library),
            "backend": self._backend,
            # https://mesonbuild.com/Builtin-options.html#base-options
            "b_vscrt": self._b_vscrt,
            "b_staticpic": to_meson_value(self._b_staticpic),
            "b_ndebug": to_meson_value(self._b_ndebug),
            # https://mesonbuild.com/Builtin-options.html#compiler-options
            "cpp_std": to_meson_value(self._cpp_std),
            "c_args": to_meson_value(self.c_args.strip().split()),
            "c_link_args": to_meson_value(self.c_link_args.strip().split()),
            "cpp_args": to_meson_value(self.cpp_args.strip().split()),
            "cpp_link_args": to_meson_value(self.cpp_link_args.strip().split()),
            "pkg_config_path": self.pkg_config_path,
            "preprocessor_definitions": self.preprocessor_definitions,
            "cross_build": self.cross_build
        }

    @property
    def content(self):
        context = self._context()
        content = Template(self._meson_file_template).render(context)
        return content

    def generate(self):
        filename = self.native_filename if not self.cross_build else self.cross_filename
        save(filename, self.content)
        # FIXME: Should we check the OS and compiler to call VCVars?
        VCVars(self._conanfile).generate()
