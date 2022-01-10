import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.apple.apple import to_apple_arch
from conan.tools.cross_building import cross_building, get_cross_building_settings
from conan.tools.env import VirtualBuildEnv
from conan.tools.microsoft import VCVars
from conans.util.files import save


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
        self._b_ndebug = "true" if self._buildtype != "Debug" else "false"

        # https://mesonbuild.com/Builtin-options.html#base-options
        fpic = self._conanfile.options.get_safe("fPIC")
        shared = self._conanfile.options.get_safe("shared")
        self._b_staticpic = fpic if (shared is False and fpic is not None) else None
        # https://mesonbuild.com/Builtin-options.html#core-options
        # Do not adjust "debug" if already adjusted "buildtype"
        self._default_library = ("shared" if shared else "static") if shared is not None else None

        compiler = (self._conanfile.settings.get_safe("compiler.base") or
                    self._conanfile.settings.get_safe("compiler"))

        cppstd = self._conanfile.settings.get_safe("compiler.cppstd")
        self._cpp_std = self._to_meson_cppstd(compiler, cppstd) if cppstd else None

        if compiler == "Visual Studio":
            vscrt = self._conanfile.settings.get_safe("compiler.base.runtime") or \
                    self._conanfile.settings.get_safe("compiler.runtime")
            self._b_vscrt = {"MD": "md",
                            "MDd": "mdd",
                            "MT": "mt",
                            "MTd": "mtd"}.get(vscrt, "none")
        elif compiler == "msvc":
            # TODO: Fill here the msvc model
            pass
        else:
            self._b_vscrt = None

        self.project_options = {}
        self.preprocessor_definitions = {}

        self.pkg_config_path = self._conanfile.generators_folder

        check_using_build_profile(self._conanfile)

        self.cross_build = {}
        default_comp = ""
        default_comp_cpp = ""
        if cross_building(conanfile):
            os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
            self.cross_build["build"] = self._to_meson_machine(os_build, arch_build)
            self.cross_build["host"] = self._to_meson_machine(os_host, arch_host)
            if hasattr(conanfile, 'settings_target') and conanfile.settings_target:
                settings_target = conanfile.settings_target
                os_target = settings_target.get_safe("os")
                arch_target = settings_target.get_safe("arch")
                self.cross_build["target"] = self._to_meson_machine(os_target, arch_target)

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

        """
        # https://mesonbuild.com/Builtin-options.html#compiler-options
        self.c_args = _to_meson_value(self._env_array('CPPFLAGS') + self._env_array('CFLAGS'))
        self.c_link_args = _to_meson_value(self._env_array('LDFLAGS'))
        self.cpp_args = _to_meson_value(self._env_array('CPPFLAGS') +
                                             self._env_array('CXXFLAGS'))
        self.cpp_link_args = _to_meson_value(self._env_array('LDFLAGS'))"""

        # TODO: What is known by the toolchain, from settings, MUST be defined here
        flags = []
        if cross_building(conanfile):
            arch = self._conanfile.settings.get_safe("arch")
            if arch:
                flags.append("-arch " + to_apple_arch(arch))
        """
        deployment_flag = apple_deployment_target_flag(self.os, self.os_version)
        sysroot_flag = " -isysroot " + self.xcrun.sdk_path
        flags = deployment_flag + sysroot_flag
        """
        self.c_args = flags
        self.c_link_args = flags
        self.cpp_args = flags
        self.cpp_link_args = flags

    @staticmethod
    def _to_meson_cppstd(compiler, cppstd):
        if compiler == "Visual Studio":
            return {'14': "'vc++14'",
                    '17': "'vc++17'",
                    '20': "'vc++latest'"}.get(cppstd, "'none'")
        return {'98': "'c++03'", 'gnu98': "'gnu++03'",
                '11': "'c++11'", 'gnu11': "'gnu++11'",
                '14': "'c++14'", 'gnu14': "'gnu++14'",
                '17': "'c++17'", 'gnu17': "'gnu++17'",
                '20': "'c++1z'", 'gnu20': "'gnu++1z'"}.get(cppstd, "'none'")

    @property
    def _context(self):

        def _to_meson_value(value):
            # https://mesonbuild.com/Machine-files.html#data-types
            if isinstance(value, str):
                return "'%s'" % value
            elif isinstance(value, bool):
                return 'true' if value else "false"
            elif isinstance(value, list):
                return '[%s]' % ', '.join([str(_to_meson_value(val)) for val in value])
            return value

        context = {
            # https://mesonbuild.com/Machine-files.html#project-specific-options
            "project_options": {k: _to_meson_value(v) for k, v in  self.project_options.items()},
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
            "buildtype": _to_meson_value(self._buildtype),
            "default_library": _to_meson_value(self._default_library),
            "backend": self._backend,
            # https://mesonbuild.com/Builtin-options.html#base-options
            "b_vscrt": self._b_vscrt,
            "b_staticpic": _to_meson_value(self._b_staticpic),
            "b_ndebug": _to_meson_value(self._b_ndebug),
            # https://mesonbuild.com/Builtin-options.html#compiler-options
            "cpp_std": self._cpp_std,
            "c_args": _to_meson_value(self.c_args),
            "c_link_args": _to_meson_value(self.c_link_args),
            "cpp_args": _to_meson_value(self.cpp_args),
            "cpp_link_args": _to_meson_value(self.cpp_link_args),
            "pkg_config_path": self.pkg_config_path,
            "preprocessor_definitions": self.preprocessor_definitions,
            "cross_build": self.cross_build
        }
        return context

    @staticmethod
    def _to_meson_machine(machine_os, machine_arch):
        # https://mesonbuild.com/Reference-tables.html#operating-system-names
        system_map = {'Android': 'android',
                      'Macos': 'darwin',
                      'iOS': 'darwin',
                      'watchOS': 'darwin',
                      'tvOS': 'darwin',
                      'FreeBSD': 'freebsd',
                      'Emscripten': 'emscripten',
                      'Linux': 'linux',
                      'SunOS': 'sunos',
                      'Windows': 'windows',
                      'WindowsCE': 'windows',
                      'WindowsStore': 'windows'}
        # https://mesonbuild.com/Reference-tables.html#cpu-families
        cpu_family_map = {'armv4': ('arm', 'armv4', 'little'),
                          'armv4i': ('arm', 'armv4i', 'little'),
                          'armv5el': ('arm', 'armv5el', 'little'),
                          'armv5hf': ('arm', 'armv5hf', 'little'),
                          'armv6': ('arm', 'armv6', 'little'),
                          'armv7': ('arm', 'armv7', 'little'),
                          'armv7hf': ('arm', 'armv7hf', 'little'),
                          'armv7s': ('arm', 'armv7s', 'little'),
                          'armv7k': ('arm', 'armv7k', 'little'),
                          'armv8': ('aarch64', 'armv8', 'little'),
                          'armv8_32': ('aarch64', 'armv8_32', 'little'),
                          'armv8.3': ('aarch64', 'armv8.3', 'little'),
                          'avr': ('avr', 'avr', 'little'),
                          'mips': ('mips', 'mips', 'big'),
                          'mips64': ('mips64', 'mips64', 'big'),
                          'ppc32be': ('ppc', 'ppc', 'big'),
                          'ppc32': ('ppc', 'ppc', 'little'),
                          'ppc64le': ('ppc64', 'ppc64', 'little'),
                          'ppc64': ('ppc64', 'ppc64', 'big'),
                          's390': ('s390', 's390', 'big'),
                          's390x': ('s390x', 's390x', 'big'),
                          'sh4le': ('sh4', 'sh4', 'little'),
                          'sparc': ('sparc', 'sparc', 'big'),
                          'sparcv9': ('sparc64', 'sparc64', 'big'),
                          'wasm': ('wasm32', 'wasm32', 'little'),
                          'x86': ('x86', 'x86', 'little'),
                          'x86_64': ('x86_64', 'x86_64', 'little')}
        system = system_map.get(machine_os, machine_os.lower())
        default_cpu_tuple = (machine_arch.lower(), machine_arch.lower(), 'little')
        cpu_tuple = cpu_family_map.get(machine_arch, default_cpu_tuple)
        cpu_family, cpu, endian = cpu_tuple[0], cpu_tuple[1], cpu_tuple[2]
        context = {
            'system': system,
            'cpu_family': cpu_family,
            'cpu': cpu,
            'endian': endian,
        }
        return context

    def generate(self):
        content = Template(self._meson_file_template).render(self._context)
        filename = self.native_filename if not self.cross_build else self.cross_filename
        save(filename, content)
        VCVars(self._conanfile).generate()
