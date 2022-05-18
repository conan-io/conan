import os
import textwrap

from jinja2 import Template

from conan.tools.apple.apple import to_apple_arch, is_apple_os, apple_min_version_flag
from conan.tools.build.cross_building import cross_building
from conan.tools.env import VirtualBuildEnv
from conan.tools.meson.helpers import *
from conan.tools.microsoft import VCVars, msvc_runtime_flag
from conans.errors import ConanException
from conans.util.files import save


class MesonToolchain(object):
    """
    MesonToolchain generator
    """

    native_filename = "conan_meson_native.ini"
    cross_filename = "conan_meson_cross.ini"

    _meson_file_template = textwrap.dedent("""
    [properties]
    {% for it, value in properties.items() -%}
    {{it}} = {{value}}
    {% endfor %}

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
    {% if buildtype %}buildtype = '{{buildtype}}'{% endif %}
    {% if debug %}debug = {{debug}}{% endif %}
    {% if default_library %}default_library = '{{default_library}}'{% endif %}
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
        """
        :param conanfile: ``< ConanFile object >`` The current recipe object. Always use ``self``.
        :param backend: ``str`` ``backend`` Meson variable value. By default, ``ninja``.
        """
        self._conanfile = conanfile
        self._os = self._conanfile.settings.get_safe("os")

        # Values are kept as Python built-ins so users can modify them more easily, and they are
        # only converted to Meson file syntax for rendering
        # priority: first user conf, then recipe, last one is default "ninja"
        self._backend = conanfile.conf.get("tools.meson.mesontoolchain:backend",
                                           default=backend or 'ninja')
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

        if compiler == "msvc":
            vscrt = msvc_runtime_flag(self._conanfile)
            self._b_vscrt = str(vscrt).lower()
        else:
            self._b_vscrt = None
        #: Dict-like object that defines Meson``properties`` with ``key=value`` format
        self.properties = {}
        #: Dict-like object that defines Meson ``project options`` with ``key=value`` format
        self.project_options = {
            "wrap_mode": "nofallback"  # https://github.com/conan-io/conan/issues/10671
        }
        #: Dict-like object that defines Meson ``preprocessor definitions``
        self.preprocessor_definitions = {}
        #: Defines the Meson ``pkg_config_path`` variable
        self.pkg_config_path = self._conanfile.generators_folder
        #: Dict-like object with the build, host, and target as the Meson machine context
        self.cross_build = {}
        default_comp = ""
        default_comp_cpp = ""
        if cross_building(conanfile, skip_x64_x86=True):
            os_host = conanfile.settings.get_safe("os")
            arch_host = conanfile.settings.get_safe("arch")
            os_build = conanfile.settings_build.get_safe('os')
            arch_build = conanfile.settings_build.get_safe('arch')
            self.cross_build["build"] = to_meson_machine(os_build, arch_build)
            self.cross_build["host"] = to_meson_machine(os_host, arch_host)
            self.properties["needs_exe_wrapper"] = True
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
        #: Defines the Meson ``c`` variable. Defaulted to ``CC`` build environment value
        self.c = build_env.get("CC") or default_comp
        #: Defines the Meson ``cpp`` variable. Defaulted to ``CXX`` build environment value
        self.cpp = build_env.get("CXX") or default_comp_cpp
        #: Defines the Meson ``c_ld`` variable. Defaulted to ``CC_LD`` or ``LD`` build
        #: environment value
        self.c_ld = build_env.get("CC_LD") or build_env.get("LD")
        #: Defines the Meson ``cpp_ld`` variable. Defaulted to ``CXX_LD`` or ``LD`` build
        #: environment value
        self.cpp_ld = build_env.get("CXX_LD") or build_env.get("LD")
        #: Defines the Meson ``ar`` variable. Defaulted to ``AR`` build environment value
        self.ar = build_env.get("AR")
        #: Defines the Meson ``strip`` variable. Defaulted to ``STRIP`` build environment value
        self.strip = build_env.get("STRIP")
        #: Defines the Meson ``as`` variable. Defaulted to ``AS`` build environment value
        self.as_ = build_env.get("AS")
        #: Defines the Meson ``windres`` variable. Defaulted to ``WINDRES`` build environment value
        self.windres = build_env.get("WINDRES")
        #: Defines the Meson ``pkgconfig`` variable. Defaulted to ``PKG_CONFIG``
        #: build environment value
        self.pkgconfig = build_env.get("PKG_CONFIG")
        #: Defines the Meson ``c_args`` variable. Defaulted to ``CFLAGS`` build environment value
        self.c_args = self._get_env_list(build_env.get("CFLAGS", []))
        #: Defines the Meson ``c_link_args`` variable. Defaulted to ``LDFLAGS`` build
        #: environment value
        self.c_link_args = self._get_env_list(build_env.get("LDFLAGS", []))
        #: Defines the Meson ``cpp_args`` variable. Defaulted to ``CXXFLAGS`` build environment value
        self.cpp_args = self._get_env_list(build_env.get("CXXFLAGS", []))
        #: Defines the Meson ``cpp_link_args`` variable. Defaulted to ``LDFLAGS`` build
        #: environment value
        self.cpp_link_args = self._get_env_list(build_env.get("LDFLAGS", []))

        # Apple flags
        #: Apple arch flag as a list, e.g., ``["-arch", "i386"]``
        self.apple_arch_flag = []
        #: Apple sysroot flag as a list, e.g., ``["-isysroot", "./Platforms/MacOSX.platform"]``
        self.apple_isysroot_flag = []
        #: Apple minimum binary version flag as a list, e.g., ``["-mios-version-min", "10.8"]``
        self.apple_min_version_flag = []

        self._resolve_apple_flags()
        self._resolve_android_cross_compilation()

    def _resolve_apple_flags(self):
        if not is_apple_os(self._os):
            return
        # SDK path is mandatory for cross-building
        sdk_path = self._conanfile.conf.get("tools.apple:sdk_path")
        if not sdk_path and self.cross_build:
            raise ConanException("You must provide a valid SDK path for cross-compilation.")

        # TODO: Delete this os_sdk check whenever the _guess_apple_sdk_name() function disappears
        os_sdk = self._conanfile.settings.get_safe('os.sdk')
        if not os_sdk and self._os != "Macos":
            raise ConanException("Please, specify a suitable value for os.sdk.")

        # Calculating the main Apple flags
        arch = to_apple_arch(self._conanfile.settings.get_safe("arch"))
        self.apple_arch_flag = ["-arch", arch] if arch else []
        self.apple_isysroot_flag = ["-isysroot", sdk_path] if sdk_path else []
        os_version = self._conanfile.settings.get_safe("os.version")
        subsystem = self._conanfile.settings.get_safe("os.subsystem")
        self.apple_min_version_flag = [apple_min_version_flag(os_version, os_sdk, subsystem)]

    def _resolve_android_cross_compilation(self):
        if not self.cross_build or not self.cross_build["host"]["system"] == "android":
            return

        ndk_path = self._conanfile.conf.get("tools.android:ndk_path")
        if not ndk_path:
            raise ConanException("You must provide a NDK path. Use 'tools.android:ndk_path' "
                                 "configuration field.")

        arch = self._conanfile.settings.get_safe("arch")
        os_build = self.cross_build["build"]["system"]
        ndk_bin = os.path.join(ndk_path, "toolchains", "llvm", "prebuilt", "{}-x86_64".format(os_build), "bin")
        android_api_level = self._conanfile.settings.get_safe("os.api_level")
        android_target = {'armv7': 'armv7a-linux-androideabi',
                          'armv8': 'aarch64-linux-android',
                          'x86': 'i686-linux-android',
                          'x86_64': 'x86_64-linux-android'}.get(arch)
        self.c = os.path.join(ndk_bin, "{}{}-clang".format(android_target, android_api_level))
        self.cpp = os.path.join(ndk_bin, "{}{}-clang++".format(android_target, android_api_level))
        self.ar = os.path.join(ndk_bin, "llvm-ar")

    def _get_extra_flags(self):
        # Now, it's time to get all the flags defined by the user
        cxxflags = self._conanfile.conf.get("tools.build:cxxflags", default=[], check_type=list)
        cflags = self._conanfile.conf.get("tools.build:cflags", default=[], check_type=list)
        sharedlinkflags = self._conanfile.conf.get("tools.build:sharedlinkflags", default=[], check_type=list)
        exelinkflags = self._conanfile.conf.get("tools.build:exelinkflags", default=[], check_type=list)
        return {
            "cxxflags": cxxflags,
            "cflags": cflags,
            "ldflags": sharedlinkflags + exelinkflags
        }

    @staticmethod
    def _get_env_list(v):
        # FIXME: Should Environment have the "check_type=None" keyword as Conf?
        return v.strip().split() if not isinstance(v, list) else v

    @staticmethod
    def _filter_list_empty_fields(v):
        return list(filter(bool, v))

    def _context(self):
        apple_flags = self.apple_isysroot_flag + self.apple_arch_flag + self.apple_min_version_flag
        extra_flags = self._get_extra_flags()

        self.c_args.extend(apple_flags + extra_flags["cflags"])
        self.cpp_args.extend(apple_flags + extra_flags["cxxflags"])
        self.c_link_args.extend(apple_flags + extra_flags["ldflags"])
        self.cpp_link_args.extend(apple_flags + extra_flags["ldflags"])

        return {
            # https://mesonbuild.com/Machine-files.html#properties
            "properties": {k: to_meson_value(v) for k, v in self.properties.items()},
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
            "buildtype": self._buildtype,
            "default_library": self._default_library,
            "backend": self._backend,
            # https://mesonbuild.com/Builtin-options.html#base-options
            "b_vscrt": self._b_vscrt,
            "b_staticpic": to_meson_value(self._b_staticpic),  # boolean
            "b_ndebug": to_meson_value(self._b_ndebug),  # boolean as string
            # https://mesonbuild.com/Builtin-options.html#compiler-options
            "cpp_std": self._cpp_std,
            "c_args": to_meson_value(self._filter_list_empty_fields(self.c_args)),
            "c_link_args": to_meson_value(self._filter_list_empty_fields(self.c_link_args)),
            "cpp_args": to_meson_value(self._filter_list_empty_fields(self.cpp_args)),
            "cpp_link_args": to_meson_value(self._filter_list_empty_fields(self.cpp_link_args)),
            "pkg_config_path": self.pkg_config_path,
            "preprocessor_definitions": self.preprocessor_definitions,
            "cross_build": self.cross_build
        }

    @property
    def _content(self):
        """
        Gets content of the file to be used by Meson as its context.

        :return: ``str`` whole Meson context content.
        """
        context = self._context()
        content = Template(self._meson_file_template).render(context)
        return content

    def generate(self):
        """
        Creates a ``conan_meson_native.ini`` (if native builds) or a
        ``conan_meson_cross.ini`` (if cross builds) with the proper content.
        If Windows OS, it will be created a ``conanvcvars.bat`` as well.
        """
        filename = self.native_filename if not self.cross_build else self.cross_filename
        save(filename, self._content)
        # FIXME: Should we check the OS and compiler to call VCVars?
        VCVars(self._conanfile).generate()
