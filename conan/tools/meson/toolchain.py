import textwrap

from jinja2 import Template

from conan.tools._check_build_profile import check_using_build_profile
from conan.tools.env import VirtualBuildEnv
from conan.tools.microsoft import VCVars
from conans.client.build.cppstd_flags import cppstd_from_settings
from conan.tools.cross_building import cross_building, get_cross_building_settings
from conans.util.files import save


class MesonToolchain(object):
    native_filename = "conan_meson_native.ini"
    cross_filename = "conan_meson_cross.ini"

    _native_file_template = textwrap.dedent("""
    [constants]
    preprocessor_definitions = [{% for it, value in preprocessor_definitions.items() -%}
    '-D{{ it }}="{{ value}}"'{%- if not loop.last %}, {% endif %}{% endfor %}]

    [project options]
    {{project_options}}

    [binaries]
    {% if c %}c = {{c}}{% endif %}
    {% if cpp %}cpp = {{cpp}}{% endif %}
    {% if c_ld %}c_ld = {{c_ld}}{% endif %}
    {% if cpp_ld %}cpp_ld = {{cpp_ld}}{% endif %}
    {% if ar %}ar = {{ar}}{% endif %}
    {% if strip %}strip = {{strip}}{% endif %}
    {% if as %}as = {{as}}{% endif %}
    {% if windres %}windres = {{windres}}{% endif %}
    {% if pkgconfig %}pkgconfig = {{pkgconfig}}{% endif %}

    [built-in options]
    {% if buildtype %}buildtype = {{buildtype}}{% endif %}
    {% if debug %}debug = {{debug}}{% endif %}
    {% if default_library %}default_library = {{default_library}}{% endif %}
    {% if b_vscrt %}b_vscrt = {{b_vscrt}}{% endif %}
    {% if b_ndebug %}b_ndebug = {{b_ndebug}}{% endif %}
    {% if b_staticpic %}b_staticpic = {{b_staticpic}}{% endif %}
    {% if cpp_std %}cpp_std = {{cpp_std}}{% endif %}
    {% if backend %}backend = {{backend}}{% endif %}
    c_args = {{c_args}} + preprocessor_definitions
    c_link_args = {{c_link_args}}
    cpp_args = {{cpp_args}} + preprocessor_definitions
    cpp_link_args = {{cpp_link_args}}
    {% if pkg_config_path %}pkg_config_path = {{pkg_config_path}}{% endif %}
    """)

    _cross_file_template = _native_file_template + textwrap.dedent("""
    [build_machine]
    {{build_machine}}

    [host_machine]
    {{host_machine}}

    [target_machine]
    {{target_machine}}
    """)

    _machine_template = textwrap.dedent("""
    system = {{system}}
    cpu_family = {{cpu_family}}
    cpu = {{cpu}}
    endian = {{endian}}
    """)

    def __init__(self, conanfile, backend=None):
        self._conanfile = conanfile
        self._backend = self._get_backend(backend)
        self._build_type = self._conanfile.settings.get_safe("build_type")
        self._base_compiler = self._conanfile.settings.get_safe("compiler.base") or \
                              self._conanfile.settings.get_safe("compiler")
        self._vscrt = self._conanfile.settings.get_safe("compiler.base.runtime") or \
                      self._conanfile.settings.get_safe("compiler.runtime")
        self._cppstd = cppstd_from_settings(self._conanfile.settings)
        self._shared = self._conanfile.options.get_safe("shared")
        self._fpic = self._conanfile.options.get_safe("fPIC")
        self._build_env = VirtualBuildEnv(self._conanfile).vars()

        self.definitions = dict()
        self.preprocessor_definitions = dict()

        def from_build_env(name):
            return self._to_meson_value(self._build_env.get(name, None))

        self.c = from_build_env("CC")
        self.cpp = from_build_env("CXX")
        self.c_ld = from_build_env("CC_LD") or from_build_env("LD")
        self.cpp_ld = from_build_env("CXX_LD") or from_build_env("LD")
        self.ar = from_build_env("AR")
        self.strip = from_build_env("STRIP")
        self.as_ = from_build_env("AS")
        self.windres = from_build_env("WINDRES")
        self.pkgconfig = from_build_env("PKG_CONFIG")

        # https://mesonbuild.com/Builtin-options.html#core-options
        # Do not adjust "debug" if already adjusted "buildtype"
        self.buildtype = self._to_meson_build_type(self._build_type) if self._build_type else None
        self.default_library = self._to_meson_shared(self._shared) \
            if self._shared is not None else None
        self.backend = self._to_meson_value(self._backend)

        # https://mesonbuild.com/Builtin-options.html#base-options
        self.b_vscrt = self._to_meson_vscrt(self._vscrt)
        self.b_staticpic = self._to_meson_value(self._fpic) \
            if (self._shared is False and self._fpic is not None) else None
        self.b_ndebug = self._to_meson_value(self._ndebug) if self._build_type else None

        # https://mesonbuild.com/Builtin-options.html#compiler-options
        self.cpp_std = self._to_meson_cppstd(self._cppstd) if self._cppstd else None
        self.c_args = self._to_meson_value(self._env_array('CPPFLAGS') + self._env_array('CFLAGS'))
        self.c_link_args = self._to_meson_value(self._env_array('LDFLAGS'))
        self.cpp_args = self._to_meson_value(self._env_array('CPPFLAGS') +
                                             self._env_array('CXXFLAGS'))
        self.cpp_link_args = self._to_meson_value(self._env_array('LDFLAGS'))
        self.pkg_config_path = "'%s'" % self._conanfile.generators_folder

        check_using_build_profile(self._conanfile)

    def _get_backend(self, recipe_backend):
        # Returns the name of the backend used by Meson
        conanfile = self._conanfile
        # Downstream consumer always higher priority
        backend_conf = conanfile.conf["tools.meson.mesontoolchain:backend"]
        if backend_conf:
            return backend_conf
        # second priority: the recipe one:
        if recipe_backend:
            return recipe_backend
        # if not defined, deduce automatically the default one (ninja)
        return 'ninja'

    @staticmethod
    def _to_meson_value(value):
        # https://mesonbuild.com/Machine-files.html#data-types
        import six

        try:
            from collections.abc import Iterable
        except ImportError:
            from collections import Iterable

        if isinstance(value, six.string_types):
            return "'%s'" % value
        elif isinstance(value, bool):
            return 'true' if value else "false"
        elif isinstance(value, six.integer_types):
            return value
        elif isinstance(value, Iterable):
            return '[%s]' % ', '.join([str(MesonToolchain._to_meson_value(v)) for v in value])
        return value

    @staticmethod
    def _to_meson_build_type(build_type):
        return {"Debug": "'debug'",
                "Release": "'release'",
                "MinSizeRel": "'minsize'",
                "RelWithDebInfo": "'debugoptimized'"}.get(build_type, "'%s'" % build_type)
    # FIXME : use 'custom' otherwise? or use just None?

    @property
    def _debug(self):
        return self._build_type == "Debug"

    @property
    def _ndebug(self):
        # ERROR: Value "True" (of type "boolean") for combo option "Disable asserts" is not one of
        # the choices. Possible choices are (as string): "true", "false", "if-release".
        return "true" if self._build_type != "Debug" else "false"

    @staticmethod
    def _to_meson_vscrt(vscrt):
        return {"MD": "'md'",
                "MDd": "'mdd'",
                "MT": "'mt'",
                "MTd": "'mtd'"}.get(vscrt, "'none'")

    @staticmethod
    def _to_meson_shared(shared):
        return "'shared'" if shared else "'static'"

    def _to_meson_cppstd(self, cppstd):
        if self._base_compiler == "Visual Studio":
            return {'14': "'vc++14'",
                    '17': "'vc++17'",
                    '20': "'vc++latest'"}.get(cppstd, "'none'")
        return {'98': "'c++03'", 'gnu98': "'gnu++03'",
                '11': "'c++11'", 'gnu11': "'gnu++11'",
                '14': "'c++14'", 'gnu14': "'gnu++14'",
                '17': "'c++17'", 'gnu17': "'gnu++17'",
                '20': "'c++1z'", 'gnu20': "'gnu++1z'"}.get(cppstd, "'none'")

    @staticmethod
    def _none_if_empty(value):
        return "'%s'" % value if value.strip() else None

    def _env_array(self, name):
        import shlex
        return shlex.split(self._build_env.get(name, ''))

    @property
    def _context(self):
        project_options = []
        for k, v in self.definitions.items():
            project_options.append("%s = %s" % (k, self._to_meson_value(v)))
        project_options = "\n".join(project_options)

        context = {
            # https://mesonbuild.com/Machine-files.html#project-specific-options
            "project_options": project_options,
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
            "buildtype": self.buildtype,
            "default_library": self.default_library,
            "backend": self.backend,
            # https://mesonbuild.com/Builtin-options.html#base-options
            "b_vscrt": self.b_vscrt,
            "b_staticpic": self.b_staticpic,
            "b_ndebug": self.b_ndebug,
            # https://mesonbuild.com/Builtin-options.html#compiler-options
            "cpp_std": self.cpp_std,
            "c_args": self.c_args,
            "c_link_args": self.c_link_args,
            "cpp_args": self.cpp_args,
            "cpp_link_args": self.cpp_link_args,
            "pkg_config_path": self.pkg_config_path,
            "preprocessor_definitions": self.preprocessor_definitions
        }
        return context

    @staticmethod
    def _render(template, context):
        t = Template(template)
        return t.render(context)

    @property
    def _native_content(self):
        return self._render(self._native_file_template, self._context)

    def _to_meson_machine(self, machine_os, machine_arch):
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
                          'armv7k':('arm', 'armv7k', 'little'),
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
            'system': self._to_meson_value(system),
            'cpu_family': self._to_meson_value(cpu_family),
            'cpu': self._to_meson_value(cpu),
            'endian': self._to_meson_value(endian),
        }
        return self._render(self._machine_template, context)

    @property
    def _cross_content(self):
        os_build, arch_build, os_host, arch_host = get_cross_building_settings(self._conanfile)
        os_target, arch_target = os_host, arch_host  # TODO: assume target the same as a host for now?

        build_machine = self._to_meson_machine(os_build, arch_build)
        host_machine = self._to_meson_machine(os_host, arch_host)
        target_machine = self._to_meson_machine(os_target, arch_target)

        context = self._context
        context['build_machine'] = build_machine
        context['host_machine'] = host_machine
        context['target_machine'] = target_machine
        return self._render(self._cross_file_template, context)

    def _write_native_file(self):
        save(self.native_filename, self._native_content)

    def _write_cross_file(self):
        save(self.cross_filename, self._cross_content)

    def generate(self):
        if cross_building(self._conanfile):
            self._write_cross_file()
        else:
            self._write_native_file()
        VCVars(self._conanfile).generate()
