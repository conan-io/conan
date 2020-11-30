import shlex
import platform
import textwrap

from io import StringIO
from jinja2 import Template
from conans import tools
from conans.errors import ConanException
from conans.util.files import save

_profile_name = 'conan'
_profiles_prefix_in_config = 'profiles.%s' % _profile_name

_architecture = {
    'x86': 'x86',
    'x86_64': 'x86_64',
    'ppc32be': 'ppc',
    'ppc32': 'ppc',
    'ppc64le': 'ppc64',
    'ppc64': 'ppc64',
    'armv4': 'arm',
    'armv4i': 'arm',
    'armv5el': 'arm',
    'armv5hf': 'arm',
    'armv6': 'arm',
    'armv7': 'arm',
    'armv7hf': 'arm',
    'armv7s': 'arm',
    'armv7k': 'arm',
    'armv8': 'arm64',
    'armv8_32': 'arm64',
    'armv8.3': 'arm64',
    'sparc': 'sparc',
    'sparcv9': 'sparc64',
    'mips': 'mips',
    'mips64': 'mips64',
    'avr': 'avr',
    's390': 's390x',
    's390x': 's390x',
    'asm.js': None,
    'wasm': None,
    'sh4le': 'sh'
}
_build_variant = {
    'Debug': 'debug',
    'Release': 'release',
    'RelWithDebInfo': 'profiling',
    'MinSizeRel': 'release'
}
_optimization = {
    'MinSizeRel': 'small'
}
_cxx_language_version = {
    '98': 'c++98',
    'gnu98': 'c++98',
    '11': 'c++11',
    'gnu11': 'c++11',
    '14': 'c++14',
    'gnu14': 'c++14',
    '17': 'c++17',
    'gnu17': 'c++17',
    '20': 'c++20',
    'gnu20': 'c++20'
}


class QbsToolchainException(ConanException):
    def __str__(self):
        msg = super(QbsToolchainException, self).__str__()
        return 'Qbs generic toolchain: {}'.format(msg)


def _bool(b):
    if b is None:
        return None

    if type(b)is not bool:
        raise QbsToolchainException(
            'Tried to convert non bool type value to bool')

    if b:
        return 'true'
    else:
        return 'false'


def _env_var_to_list(var):
    return list(shlex.shlex(var, posix=True, punctuation_chars=True))


def _check_for_compiler(conanfile):
    compiler = conanfile.settings.get_safe('compiler')
    if not compiler:
        raise QbsToolchainException('need compiler to be set in settings')

    if compiler not in ['Visual Studio', 'gcc', 'clang']:
        raise QbsToolchainException('compiler not supported')


def _default_compiler_name(conanfile):
    # needs more work since currently only windows and linux is supported
    compiler = conanfile.settings.get_safe('compiler')
    the_os = conanfile.settings.get_safe('os')
    if the_os == 'Windows':
        if compiler == 'gcc':
            return 'mingw'
        if compiler == 'Visual Studio':
            if tools.msvs_toolset(conanfile) == 'ClangCl':
                return 'clang-cl'
            return 'cl'
        if compiler == 'clang':
            return 'clang-cl'
        raise QbsToolchainException('unknown windows compiler')

    return compiler


def _settings_dir(conanfile):
    return '%s/conan_qbs_toolchain_settings_dir' % conanfile.install_folder


def _setup_toolchains(conanfile):
    if tools.get_env('CC'):
        compiler = tools.get_env('CC')
    else:
        compiler = _default_compiler_name(conanfile)

    env_context = tools.no_op()
    if platform.system() == 'Windows':
        if compiler in ['cl', 'clang-cl']:
            env_context = tools.vcvars()

    with env_context:
        cmd = 'qbs-setup-toolchains --settings-dir "%s" %s %s' % (
              _settings_dir(conanfile), compiler, _profile_name)
        conanfile.run(cmd)


def _read_qbs_toolchain_from_config(conanfile):
    s = StringIO()
    conanfile.run('qbs-config --settings-dir "%s" --list' % (
                    _settings_dir(conanfile)), output=s)
    config = {}
    s.seek(0)
    for line in s:
        colon = line.index(':')
        if 0 < colon and not line.startswith('#'):
            full_key = line[:colon]
            if full_key.startswith(_profiles_prefix_in_config):
                key = full_key[len(_profiles_prefix_in_config)+1:]
                value = line[colon+1:].strip()
                if value.startswith('"') and value.endswith('"'):
                    temp_value = value[1:-1]
                    if (temp_value.isnumeric() or
                            temp_value in ['true', 'false', 'undefined']):
                        value = temp_value
                config[key] = value
    return config


class LinkerFlagsParser(object):
    def __init__(self, ld_flags):
        self.driver_linker_flags = []
        self.linker_flags = []
        self._parse = self._detect_wl_or_add_driver_linker_flag
        for token in ld_flags:
            self._parse(token)

    def _detect_wl_or_add_driver_linker_flag(self, token):
        if token == '-Wl':
            self._parse = self._assert_comma
        else:
            self.driver_linker_flags.append(token)
            self._parse = self._detect_wl_or_add_driver_linker_flag

    def _detect_wl_or_detect_comma_or_add_driver_linker_flag(self, token):
        if token == ',':
            self._parse = self._add_linker_flag
        else:
            self._detect_wl_or_add_driver_linker_flag(token)

    def _assert_comma(self, token):
        if token != ',':
            raise QbsToolchainException('Could not parse LDFLAGS')
        self._parse = self._add_linker_flag

    def _add_linker_flag(self, token):
        self.linker_flags.append(token)
        self._parse = self._detect_wl_or_detect_comma_or_add_driver_linker_flag


def _flags_from_env():
    flags_from_env = {}
    if tools.get_env('ASFLAGS'):
        flags_from_env['cpp.assemblerFlags'] = '%s' % (
            _env_var_to_list(tools.get_env('ASFLAGS')))
    if tools.get_env('CFLAGS'):
        flags_from_env['cpp.cFlags'] = '%s' % (
            _env_var_to_list(tools.get_env('CFLAGS')))
    if tools.get_env('CPPFLAGS'):
        flags_from_env['cpp.cppFlags'] = '%s' % (
            _env_var_to_list(tools.get_env('CPPFLAGS')))
    if tools.get_env('CXXFLAGS'):
        flags_from_env['cpp.cxxFlags'] = '%s' % (
            _env_var_to_list(tools.get_env('CXXFLAGS')))
    if tools.get_env('LDFLAGS'):
        parser = LinkerFlagsParser(_env_var_to_list(tools.get_env('LDFLAGS')))
        flags_from_env['cpp.linkerFlags'] = str(parser.linker_flags)
        flags_from_env['cpp.driverLinkerFlags'] = str(
            parser.driver_linker_flags)
    return flags_from_env


class QbsGenericToolchain(object):
    filename = 'conan_toolchain.qbs'

    _template_toolchain = textwrap.dedent('''\
        import qbs

        Project {
            Profile {
                name: "conan_toolchain_profile"

                /* detected via qbs-setup-toolchains */
                {%- for key, value in _profile_values_from_setup.items() %}
                {{ key }}: {{ value }}
                {%- endfor %}

                /* deduced from environment */
                {%- for key, value in _profile_values_from_env.items() %}
                {{ key }}: {{ value }}
                {%- endfor %}
                {%- if sysroot %}
                qbs.sysroot: "{{ sysroot }}"
                {%- endif %}

                /* conan settings */
                {%- if build_variant %}
                qbs.buildVariant: "{{ build_variant }}"
                {%- endif %}
                {%- if architecture %}
                qbs.architecture: "{{ architecture }}"
                {%- endif %}
                {%- if optimization %}
                qbs.optimization: "{{ optimization }}"
                {%- endif %}
                {%- if cxx_language_version %}
                cpp.cxxLanguageVersion: "{{ cxx_language_version }}"
                {%- endif %}

                /* package options */
                {%- if position_independent_code %}
                cpp.positionIndependentCode: {{ position_independent_code }}
                {%- endif %}
            }
        }
        ''')

    def __init__(self, conanfile):
        _check_for_compiler(conanfile)
        self._conanfile = conanfile
        _setup_toolchains(conanfile)
        self._profile_values_from_setup = (
            _read_qbs_toolchain_from_config(conanfile))
        self._profile_values_from_env = _flags_from_env()
        tools.rmdir(_settings_dir(conanfile))

        self._architecture = _architecture.get(
            conanfile.settings.get_safe('arch'))
        self._build_variant = _build_variant.get(
            conanfile.settings.get_safe('build_type'))
        self._optimization = _optimization.get(
            conanfile.settings.get_safe('build_type'))
        self._cxx_language_version = _cxx_language_version.get(
            str(conanfile.settings.get_safe('compiler.cppstd')))
        self._sysroot = tools.get_env('SYSROOT')
        self._position_independent_code = _bool(
            conanfile.options.get_safe('fPIC'))

    def generate(self):
        save(self.filename, self.content)

    @property
    def content(self):
        context = {
            '_profile_values_from_setup': self._profile_values_from_setup,
            '_profile_values_from_env': self._profile_values_from_env,
            'build_variant': self._build_variant,
            'architecture': self._architecture,
            'optimization': self._optimization,
            'sysroot': self._sysroot,
            'position_independent_code': self._position_independent_code,
            'cxx_language_version': self._cxx_language_version
        }
        t = Template(self._template_toolchain)
        content = t.render(**context)
        return content
