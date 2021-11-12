import shlex
import shutil
import platform
import textwrap

from io import StringIO
from jinja2 import Template
from conans.errors import ConanException
from conan.tools.env import VirtualBuildEnv
from conan.tools.microsoft import MSBuildToolchain, VCVars
from conans.util.files import save


class LinkerFlagsParser(object):
    def __init__(self, ld_flags):
        self.driver_linker_flags = []
        self.linker_flags = []

        for item in ld_flags:
            if item.startswith('-Wl'):
                self.linker_flags.extend(item.split(',')[1:])
            else:
                self.driver_linker_flags.append(item)


class QbsProfile(object):
    filename = 'conan_toolchain_profile.qbs'
    old_filename = 'conan_toolchain.qbs'

    _profile_name = 'conan'
    _profiles_prefix_in_config = 'profiles.%s' % _profile_name

    _architecture_map = {
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
    _build_variant_map = {
        'Debug': 'debug',
        'Release': 'release',
        'RelWithDebInfo': 'profiling',
        'MinSizeRel': 'release'
    }
    _optimization_map = {
        'MinSizeRel': 'small'
    }
    _cxx_language_version_map = {
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
    _target_platform_map = {
        'Windows': 'windows',
        'WindowsStore': 'windows',
        'WindowsCE': 'windows',
        'Linux': 'linux',
        'Macos': 'macos',
        'Android': 'android',
        'iOS': 'ios',
        'watchOS': 'watchos',
        'tvOS': 'tvos',
        'FreeBSD': 'freebsd',
        'SunOS': 'solaris',
        'AIX': 'aix',
        'Emscripten': None,
        'Arduino': 'none',
        'Neutrino': 'qnx',
    }
    _runtime_library_map = {
        'static': 'static',
        'dynamic': 'dynamic',
        'MD': 'dynamic',
        'MT': 'static',
        'MDd': 'dynamic',
        'MTd': 'static',
    }

    _template_profile = textwrap.dedent('''\
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
                {%- if not _profile_values_from_setup["qbs.targetPlatform"] %}
                {%- if target_platform %}
                qbs.targetPlatform: "{{ target_platform }}"
                {%- else %}
                qbs.targetPlatform: undefined
                {%- endif %}
                {%- endif %}
                {%- if optimization %}
                qbs.optimization: "{{ optimization }}"
                {%- endif %}
                {%- if cxx_language_version %}
                cpp.cxxLanguageVersion: "{{ cxx_language_version }}"
                {%- endif %}
                {%- if runtime_library %}
                cpp.runtimeLibrary: "{{ runtime_library }}"
                {%- endif %}

                /* package options */
                {%- if position_independent_code %}
                cpp.positionIndependentCode: {{ position_independent_code }}
                {%- endif %}
            }
        }
        ''')

    def __init__(self, conanfile):
        self._init(conanfile)

    def generate(self):
        save(self.old_filename, self.content)
        save(self.filename, self.content)

    @property
    def content(self):
        context = {
            '_profile_values_from_setup': self._profile_values_from_setup,
            '_profile_values_from_env': self._profile_values_from_env,
            'build_variant': self._build_variant,
            'architecture': self._architecture if not
            self._profile_values_from_setup.get("qbs.architecture") else None,
            'optimization': self._optimization,
            'sysroot': self._sysroot,
            'position_independent_code': self._position_independent_code,
            'cxx_language_version': self._cxx_language_version,
            'target_platform': self._target_platform,
            'runtime_library': self._runtime_library,
        }
        t = Template(self._template_profile)
        content = t.render(**context)
        return content

    def _bool(self, b):
        return None if b is None else str(b).lower()

    def _init(self, conanfile):
        self._conanfile = conanfile
        self._check_for_compiler()
        build_env = self._get_build_env()
        self._setup_toolchains(build_env)
        self._profile_values_from_setup = (
            self._read_qbs_profile_from_config())
        self._profile_values_from_env = self._flags_from_env(build_env)
        shutil.rmtree(self._settings_dir())

        self._architecture = self._architecture_map.get(
            conanfile.settings.get_safe('arch'))
        self._build_variant = self._build_variant_map.get(
            conanfile.settings.get_safe('build_type'))
        self._optimization = self._optimization_map.get(
            conanfile.settings.get_safe('build_type'))
        self._cxx_language_version = self._cxx_language_version_map.get(
            str(conanfile.settings.get_safe('compiler.cppstd')))
        self._target_platform = self._target_platform_map.get(
            conanfile.settings.get_safe('os'))
        self._runtime_library = self._runtime_library_map.get(
            conanfile.settings.get_safe('compiler.runtime'))
        self._sysroot = build_env.get('SYSROOT')
        self._position_independent_code = self._bool(
            conanfile.options.get_safe('fPIC'))

    def _get_build_env(self):
        virtual_build_env = VirtualBuildEnv(self._conanfile)
        return virtual_build_env.environment()

    def _env_var_to_list(self, var):
        return shlex.split(var)

    def _check_for_compiler(self):
        compiler = self._conanfile.settings.get_safe('compiler')
        if not compiler:
            raise ConanException('Qbs: need compiler to be set in settings')

        if compiler not in ['Visual Studio', 'gcc', 'clang']:
            raise ConanException('Qbs: compiler {} not supported'.format(compiler))

    def _default_compiler_name(self):
        # needs more work since currently only windows and linux is supported
        compiler = self._conanfile.settings.get_safe('compiler')
        the_os = self._conanfile.settings.get_safe('os')
        if the_os == 'Windows':
            if compiler == 'gcc':
                return 'mingw'
            if compiler == 'Visual Studio':
                if MSBuildToolchain._msvs_toolset(self._conanfile.settings) == 'ClangCL':
                    return 'clang-cl'
                return 'cl'
            if compiler == 'msvc':
                return 'cl'
            if compiler == 'clang':
                return 'clang-cl'
            raise ConanException('unknown windows compiler')

        return compiler

    def _settings_dir(self):
        return '%s/conan_qbs_toolchain_settings_dir' % self._conanfile.install_folder

    def _setup_toolchains(self, build_env):
        if build_env.get('CC'):
            compiler = build_env.get('CC')
        else:
            compiler = self._default_compiler_name()

        env = None
        if platform.system() == 'Windows':
            if compiler in ['cl', 'clang-cl']:
                VCVars(self._conanfile).generate(group=None)
                env = "conanvcvars"

        cmd = 'qbs-setup-toolchains --settings-dir "%s" %s %s' % (
            self._settings_dir(), compiler, self._profile_name)
        self._conanfile.run(cmd, env=env)

    def _read_qbs_profile_from_config(self):
        s = StringIO()
        self._conanfile.run('qbs-config --settings-dir "%s" --list' % (
            self._settings_dir()), output=s)
        config = {}
        s.seek(0)
        for line in s:
            colon = line.index(':')
            if 0 < colon and not line.startswith('#'):
                full_key = line[:colon]
                if full_key.startswith(self._profiles_prefix_in_config):
                    key = full_key[len(self._profiles_prefix_in_config)+1:]
                    value = line[colon+1:].strip()
                    if value.startswith('"') and value.endswith('"'):
                        temp_value = value[1:-1]
                        if (temp_value.isnumeric() or
                                temp_value in ['true', 'false', 'undefined']):
                            value = temp_value
                    config[key] = value
        return config

    def _flags_from_env(self, build_env):
        flags_from_env = {}
        if build_env.get('ASFLAGS'):
            flags_from_env['cpp.assemblerFlags'] = '%s' % (
                self._env_var_to_list(build_env.get('ASFLAGS')))
        if build_env.get('CFLAGS'):
            flags_from_env['cpp.cFlags'] = '%s' % (
                self._env_var_to_list(build_env.get('CFLAGS')))
        if build_env.get('CPPFLAGS'):
            flags_from_env['cpp.cppFlags'] = '%s' % (
                self._env_var_to_list(build_env.get('CPPFLAGS')))
        if build_env.get('CXXFLAGS'):
            flags_from_env['cpp.cxxFlags'] = '%s' % (
                self._env_var_to_list(build_env.get('CXXFLAGS')))
        if build_env.get('LDFLAGS'):
            parser = LinkerFlagsParser(self._env_var_to_list(build_env.get('LDFLAGS')))
            flags_from_env['cpp.linkerFlags'] = str(parser.linker_flags)
            flags_from_env['cpp.driverLinkerFlags'] = str(
                parser.driver_linker_flags)
        return flags_from_env
