import os
import platform
from configparser import ConfigParser
from pathlib import Path

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.cppstd_flags import cppstd_from_settings
from conans.client.tools.env import environment_append, _environment_add, no_op
from conans.client.tools.oss import args_to_string
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB
from conans.model.version import Version
from conans.util.files import decode_text, get_abs_path, mkdir
from conans.util.runners import version_runner

# TODO:
# - add pkg_config_path to configure (cross scenario and native)
# - fix env variables reading for native\cross
# - cleanup comments
# - add tests
# - remove _ss from MesonX __init__()

# Differences from stock Meson integration:
# - does not override 'default_library' if no 'shared' options was set
# - saves `build_dir` in __init__
# - cleaned up interface: removed old arguments, removed build_dir and etc
# - added machine file support
# - added machine file generation for `toolchain`
# - backend-agnostic meson methods are used by default with ninja as a fallback for older meson versions.
# - env variables with dependency search paths are not appended when executing meson commands
# - requires pkg-config generator
# - removed args kwarg from configure

# Question:
# - Should we keep `cross-file`/`native-file` kwarg?
# - Should we generate and use the default toolchain by default? If so, how should that be done?

class MesonMachineFile:
    def __init__(self,
                 name: str,
                 path: str = None,
                 config: ConfigParser = None):
        if not name:
            raise ConanException('`name` is empty: machine file must have a unique name supplied')
        self.name = name

        if path and config:
            raise ConanException('Both `path` and `config` were supplied: only one should be used')
        if path:
            config = ConfigParser()
            config.read(path)
        self.options = config

    def dump(self, output: str):
        outpath = Path(output)
        if not outpath.exists():
            outpath.mkdir(parents=True)
        with open(outpath/self.name, 'w') as f:
            self.options.write(f)

class MesonToolchain:
    def __init__(self, native_files = None, cross_files = None ):
        self.native_files = native_files or []
        self.cross_files = cross_files or []

    def __iter__(self):
        for i in [self.native_files, self.cross_files]:
            yield i

    def dump(self, output: str):
        def dump_files(files, outpath: str):
            if not files:
                pass
            if not outpath.exists():
                outpath.mkdir(parents=True)
            for f in self.native_files:
                f.dump(outpath)

        dump_files(self.native_files, Path(output) / 'native')
        dump_files(self.cross_files, Path(output) / 'cross')

class MesonDefaultToolchainGenerator(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self, force_cross: bool = False) -> MesonToolchain:
        mt = MesonToolchain()
        has_settings_build = hasattr(self._conanfile, 'settings_build') and self._conanfile.settings_build
        has_settings_target = hasattr(self._conanfile, 'settings_target') and self._conanfile.settings_target
        if has_settings_build:
            mt.native_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_native(self._conanfile.settings_build, True)))]
        if has_settings_target:
            mt.cross_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_cross(self._conanfile.settings_target)))]
        if not has_settings_build and not has_settings_target:
            tmp_native_files, tmp_cross_files = self._create_machine_files_from_settings(self._conanfile.settings, force_cross)
            mt.native_files += tmp_native_files
            mt.cross_files += tmp_cross_files
        return mt

    def _dict_to_config(self, machine_dict: dict) -> ConfigParser:
        config = ConfigParser()
        config.read_dict(self._to_ini(machine_dict))
        return config

    def _to_ini(self, config):
        return {
            section_name: {
                key: self._to_ini_value(value) for key, value in section.items() if value is not None
            } for section_name, section in config.items()
        }

    def _to_ini_value(self, value):
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str):
            return "'{}'".format(value)
        return value

    def _create_native(self, settings, is_separate_profile: bool) -> dict:
        def none_if_empty(input: str):
            stripped_input = input.strip()
            return stripped_input if stripped_input else None
        def env_or_for_build(input: str, is_separate_profile, default_val = None):
            if is_separate_profile:
                return os.environ.get(input, default_val)
            else:
                return os.environ.get('{}_FOR_BUILD'.format(input), default_val)
        def atr_or_for_build(settings, input: str, is_separate_profile):
            if is_separate_profile:
                return settings.get_safe(input)
            else:
                return settings.get_safe('{}_build'.format(input))

        config_template = {
            'binaries': {
                'c': env_or_for_build('CC', is_separate_profile),
                'cpp': env_or_for_build('CXX', is_separate_profile),
                'ld': env_or_for_build('LD', is_separate_profile),
                'ar': env_or_for_build('AR', is_separate_profile),
                'strip': env_or_for_build('STRIP', is_separate_profile),
                'as': env_or_for_build('AS', is_separate_profile),
                'ranlib': env_or_for_build('RANLIB', is_separate_profile),
                'pkgconfig': tools.which('pkg-config')
            },
            'properties': {
                'c_args': none_if_empty(env_or_for_build('CPPFLAGS', is_separate_profile, '') + ' ' + env_or_for_build('CFLAGS', is_separate_profile, '')),
                'cpp_args': none_if_empty(env_or_for_build('CPPFLAGS', is_separate_profile, '') + ' ' + env_or_for_build('CXXFLAGS', is_separate_profile, '')),
                'c_link_args': env_or_for_build('LDFLAGS', is_separate_profile),
                'cpp_link_args': env_or_for_build('LDFLAGS', is_separate_profile),
                'pkg_config_path': env_or_for_build('PKG_CONFIG_PATH', is_separate_profile),
            }
        }

        if atr_or_for_build(settings, 'os', is_separate_profile):
            resolved_os = atr_or_for_build(settings, 'os', is_separate_profile)
            arch = atr_or_for_build(settings, 'arch', is_separate_profile)
            cpu_family, endian = self._get_cpu_family_and_endianness_from_arch(str(arch))
            config_template['build_machine'] = {
                'system': self._get_system_from_os(str(resolved_os)),
                'cpu': str(arch),
                'cpu_family': cpu_family,
                'endian': endian,
            }

        return config_template

    def _create_cross(self, settings) -> dict:
        def none_if_empty(input: str):
            stripped_input = input.strip()
            return stripped_input if stripped_input else None

        config_template = {
            'binaries': {
                'c': os.environ.get('CC'),
                'cpp': os.environ.get('CXX'),
                'ld': os.environ.get('LD'),
                'ar': os.environ.get('AR'),
                'strip': os.environ.get('STRIP'),
                'as': os.environ.get('AS'),
                'ranlib': os.environ.get('RANLIB'),
                'pkgconfig': tools.which('pkg-config')
            },
            'properties': {
                'c_args': none_if_empty(os.environ.get('CPPFLAGS', '') + ' ' + os.environ.get('CFLAGS', '')),
                'cpp_args': none_if_empty(os.environ.get('CPPFLAGS', '') + ' ' + os.environ.get('CXXFLAGS', '')),
                'c_link_args': os.environ.get('LDFLAGS'),
                'cpp_link_args': os.environ.get('LDFLAGS'),
                'pkg_config_path': os.environ.get('PKG_CONFIG_PATH'),
                'needs_exe_wrapper': tools.cross_building(settings),
            },
            'host_machine': {
                'system': self._get_system_from_os(str(settings.os)),
                'cpu': str(settings.arch)
            }
        }

        cpu_family, endian = self._get_cpu_family_and_endianness_from_arch(str(settings.arch))
        config_template['host_machine']['cpu_family'] = cpu_family
        config_template['host_machine']['endian'] = endian

        if not config_template['binaries']['c'] and not config_template['binaries']['cpp']:
            raise ConanException(f'CC and CXX are undefined: C or C++ compiler must be defined when cross-building')

        return config_template

    def _create_machine_files_from_settings(self, settings, force_cross: bool):
        is_cross = force_cross
        has_for_build = False

        if not is_cross:
            has_for_build = any(map(lambda e: os.environ.get(e), ['CC_FOR_BUILD', 'CXX_FOR_BUILD']))
            is_cross = has_for_build or any(map(lambda a: hasattr(settings, a), ['os_build', 'arch_build']))

        native_files = []
        if has_for_build or not is_cross:
            native_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_native(settings, False)))]

        cross_files = []
        if is_cross:
            cross_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_cross(settings)))]

        return (native_files, cross_files)

    @staticmethod
    def _get_system_from_os(os: str) -> str:
        """
        Converts from `conan/conans/client/conf/__init__.py` to `https://mesonbuild.com/Reference-tables.html#operating-system-names`
        """
        os = os.lower()
        if (os == 'macos' or os == 'ios'):
            return 'darwin'
        else:
            return os

    @staticmethod
    def _get_cpu_family_and_endianness_from_arch(arch: str):
        """
        Converts from `conan/conans/client/conf/__init__.py` to `https://mesonbuild.com/Reference-tables.html#cpu-families`
        """
        arch_to_cpu = {
            'x86' : ('x86', 'little'),
            'x86_64' : ('x86_64',  'little'),
            'x86' : ('x86', 'little'),
            'ppc32be' : ('ppc', 'big'),
            'ppc32' : ('ppc', 'little'),
            'ppc64le' : ('ppc64', 'little'),
            'ppc64' : ('ppc64', 'big'),
            'armv4' : ('arm', 'little'),
            'armv4i' : ('arm', 'little'),
            'armv5el' : ('arm', 'little'),
            'armv5hf' : ('arm', 'little'),
            'armv6' : ('arm', 'little'),
            'armv7' : ('arm', 'little'),
            'armv7hf' : ('arm', 'little'),
            'armv7s' : ('arm', 'little'),
            'armv7k' : ('arm', 'little'),
            'armv8_32' : ('arm', 'little'),
            'armv8' : ('aarch64', 'little'),
            'armv8.3' : ('aarch64', 'little'),
            'sparc' : ('sparc', 'big'),
            'sparcv9' : ('sparc64', 'big'),
            'mips' : ('mips', 'big'),
            'mips64' : ('mips64', 'big'),
            'avr' : ('avr', 'little'),
            's390' : ('s390', 'big'),
            's390x' : ('s390', 'big'),
            'wasm' : ('wasm', 'little'),
        }

        if (arch not in arch_to_cpu):
            raise ConanException('Unknown arch: {}'.format(arch))

        return arch_to_cpu[arch]

class MesonX(object):
    def __init__(self, conanfile, build_dir: str = None, backend: str = None, append_vcvars: boolean = False) -> None:
        if self.get_version() < '0.42.0':
            raise ConanException('`meson` is too old: minimum required version `0.42.0` vs current version `{}`'.format(self.get_version()))
        if not 'pkg_config' in conanfile.generators:
            raise ConanException('`pkg_config` generator is required for `meson` integration')

        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._append_vcvars = append_vcvars
        self._build_dir = build_dir
        self._build_type = self._ss('build_type')

        # Needed for internal checks
        self._os = self._ss('os')
        self._compiler = self._ss('compiler')

        # Meson recommends to use ninja by default
        self.backend = backend or 'ninja'

    @staticmethod
    def get_version() -> Version:
        try:
            out = version_runner(['meson', '--version'])
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException('Error retrieving Meson version: `{}`'.format(e))

    @property
    def build_folder(self) -> str:
        return self.build_dir

    def get_default_toolchain(self, force_cross: boolean = False) -> MesonToolchain:
        """
        Should be used in the recipe's `toolchain()` method
        """
        return MesonDefaultToolchainGenerator(self._conanfile).generate(force_cross)

    def configure(self, source_folder=None, cache_build_folder=None, build_type=None, pkg_config_paths=None, native_files=None, cross_files=None, options=None, args=None):
        if not self._conanfile.should_configure:
            return

        args = args or []
        options = options or []
        native_files = native_files or []
        cross_files = cross_files or []

        def check_arg_not_in_opts_or_args(arg_name, use_instead_msg):
            if arg_name in options:
                raise ConanException('Don\'t pass `{}` via `options`: {}'.format(arg_name, use_instead_msg))
            if any(map(lambda a: a.startswith('--{}'.format(arg_name)) or a.startswith('-D{}'.format(arg_name)), args)):
                raise ConanException('Don\'t pass `{}` via `args`: {}'.format(arg_name, use_instead_msg))

        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder, cache_build_folder)
        mkdir(self.build_dir)

        resolved_options = self._get_default_options()
        # overwrite default values with user's inputs
        resolved_options.update(options)

        check_arg_not_in_opts_or_args('backend', 'use `backend` kwarg in the class constructor instead')
        resolved_options.update({'backend': '{}'.format(self.backend)})

        check_arg_not_in_opts_or_args('buildtype', 'use `build_type` kwarg instead')
        settings_bulld_type = self._settings.get_safe('build_type')
        if build_type and build_type != settings_bulld_type:
            self._conanfile.output.warn(
                'Set build type "{}" is different than the settings build_type "{}"'.format(build_type, settings_bulld_type))
        resolved_build_type = build_type or settings_bulld_type
        if resolved_build_type:
            resolved_options.update({'buildtype': '{}'.format(resolved_build_type)})

        check_arg_not_in_opts_or_args('pkg_config_path', 'use `pkg_config_paths` kwarg instead')
        pc_paths = [self._conanfile.install_folder]
        if pkg_config_paths:
            pc_paths += [get_abs_path(f, self._conanfile.install_folder) for f in pkg_config_paths]
        resolved_options.update({'pkg_config_path': '{}'.format(os.pathsep.join(pc_paths))})

        check_arg_not_in_opts_or_args('native-file', 'use `native_files` kwarg instead')
        check_arg_not_in_opts_or_args('cross-file', 'use `cross_files` kwarg instead')
        resolved_native_files = self._get_default_machine_files('native') + native_files
        resolved_cross_files = self._get_default_machine_files('cross') + cross_files
        if resolved_native_files:
            resolved_options['native-file'] = resolved_native_files
        if resolved_cross_files:
            resolved_options['cross-file'] = resolved_cross_files

        arg_list = join_arguments([
            self._options_to_string(resolved_options),
            args_to_string(args),
        ])

        env_vars_to_clean = {
            'CC',
            'CXX',
            'LD',
            'CCFLAGS',
            'CXXFLAGS',
            'CPPFLAGS',
            'LDFLAGS',
            'AR',
            'AS',
            'STRIP',
            'RANLIB',
        }
        clean_env = {ev: None for ev in env_vars_to_clean}
        clean_env.update({'{}_FOR_BUILD'.format(ev): None for ev in env_vars_to_clean})

        with environment_append(clean_env):
            self._run('meson setup "{}" "{}" {}'.format(source_dir, self.build_dir, arg_list))

    def build(self, args=None, targets=None):
        if not self._conanfile.should_build:
            return

        args = args or []
        targets = targets or []

        minimum_version = '0.55.0' if targets else '0.54.0'
        if self.get_version() >= minimum_version:
            combined_args = targets + args # order is important, since args might contain `-- -posix-like -positional-args`
            self._run_meson_command(subcommand='compile', args=combined_args)
        else:
            self._validate_ninja_usage_and_warn_agnostic_method_unavailable(minimum_version)
            meson_target = next( (t for t in targets if ':' in t), None)
            if meson_target:
                raise ConanException('Your targets contain meson syntax which is not supported by ninja: `{}`'.format(meson_target))
            self._run_ninja_targets(targets=targets,
                                    args=self._filter_non_ninja_args(args=args,
                                                                     ninja_args=['--verbose', '-v', '-j*', '-l*']))

    def install(self, args=None):
        if not self._conanfile.should_install:
            return

        args = args or []

        minimum_version = '0.47.0'
        if self.get_version() >= minimum_version:
            self._run_meson_command(subcommand='install', args=args)
        else:
            self._validate_ninja_usage_and_warn_agnostic_method_unavailable(minimum_version)
            self._run_ninja_targets(targets=['install'],
                                    args=self._filter_non_ninja_args(args=args))

    def test(self, args=None):
        if not self._conanfile.should_test:
            return

        args = args or []

        self._run_meson_command(subcommand='test', args=args)

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _so(self, setname):
        """safe option"""
        return self._conanfile.options.get_safe(setname)

    def _validate_ninja_usage_and_warn_agnostic_method_unavailable(self, minimum_version: str):
        if self.backend != 'ninja':
            raise ConanException('This method is not implemented yet for `{}` backend. Change your backend to `ninja` or update your `meson`.\n'.format(self.backend) +
                                 'Minimum required `meson` version is {}'.format(minimum_version))
        self._conanfile.output.warn(
            'Backend agnostic version of this method is not supported on this `meson` version. Using `ninja` directly instead.\n'
            'Minimum required `meson` version is {}'.format(minimum_version))

    def _filter_non_ninja_args(self, args=None, ninja_args=None):
        if not args:
            return []

        args = args or []
        ninja_args = ninja_args or []

        filtered_args = []
        remaining_args = []
        for a in args:
            for n in ninja_args:
                if (n.endswith('*') and a.startswith(n[:-1])) or a == n:
                    filtered_args += [a]
                else:
                    remaining_args += [a]

        if remaining_args:
            self._conanfile.output.warn(
                'The following `meson` args are not supported by `ninja` and will be ignored: "{}"'.format(' '.join(remaining_args)))

        return filtered_args

    def _get_dirs(self, source_folder, build_folder, cache_build_folder):
        build_ret = get_abs_path(build_folder, self._conanfile.build_folder)
        source_ret = get_abs_path(source_folder, self._conanfile.source_folder)

        if self._conanfile.in_local_cache and cache_build_folder:
            build_ret = get_abs_path(cache_build_folder, self._conanfile.build_folder)

        return source_ret, build_ret

    def _get_default_options(self) -> dict:
        options = dict()
        if self._conanfile.package_folder:
            options['prefix'] = self._conanfile.package_folder
        options['libdir'] = DEFAULT_LIB
        options['bindir'] = DEFAULT_BIN
        options['sbindir'] = DEFAULT_BIN
        options['libexecdir'] = DEFAULT_BIN
        options['includedir'] = DEFAULT_INCLUDE

        cppstd = cppstd_from_settings(self._conanfile.settings)
        cppstd_conan2meson = {
            '98': 'c++03', 'gnu98': 'gnu++03',
            '11': 'c++11', 'gnu11': 'gnu++11',
            '14': 'c++14', 'gnu14': 'gnu++14',
            '17': 'c++17', 'gnu17': 'gnu++17',
            '20': 'c++1z', 'gnu20': 'gnu++1z'
        }
        if cppstd:
            options['cpp_std'] = cppstd_conan2meson[cppstd]

        shared = self._so('shared')
        if shared != None:
            options['default_library'] = shared

        if self._os and 'Windows' not in self._os:
            fpic = self._so('fPIC')
            if fpic != None:
                shared = self._so('shared')
                options['b_staticpic'] = fpic or shared

        return options

    def _get_default_machine_files(self, machine_file_type: str):
        """
        Get all native files in the build_dir
        """
        bdir = Path(self.build_dir)
        if not bdir.exists:
            raise ConanException('Build directory does not exist: `{}`'.format(self.build_dir))
        machine_file_path = bdir / machine_file_type
        return list(machine_file_path.glob('*')) if machine_file_path.exists else []

    def _options_to_string(self, options):
        return ' '.join([self._option_to_string(k, v) for k, v in options.items()])
    
    @staticmethod
    def _option_to_string(key, value):
        if isinstance(value, list):
            # "-Doption=['a,1', 'b']"
            return '"-D{}={}"'.format(key, ', '.join(['\'{}\''.format(v) for v in value]))
        else:
            return '-D{}="{}"'.format(key, value)

    @staticmethod
    def _get_meson_buildtype(build_type):
        build_types = {'RelWithDebInfo': 'debugoptimized',
                       'MinSizeRel': 'release',
                       'Debug': 'debug',
                       'Release': 'release'}
        if build_type not in build_types:
            raise ConanException('Unknown build type: {}'.format(build_type))
        return build_types[build_type]

    @property
    def _vcvars_needed(self):
        return (self._compiler == 'Visual Studio' and self.backend == 'ninja' and
                platform.system() == 'Windows')

    def _run(self, command):
        if self._vcvars_needed:
            vcvars_dict = tools.vcvars_dict(self._settings, output=self._conanfile.output)
            cm = _environment_add(vcvars_dict, post=self._append_vcvars)
        else:
            cm = no_op()
        with cm:
            self._conanfile.run(command)

    def _run_ninja_targets(self, targets=None, args=None):
        if self.backend != 'ninja':
            raise ConanException('Internal error: this command should not be invoked non-`ninja` backend')

        targets = targets or []
        args = args or []

        build_dir = self.build_dir or self._conanfile.build_folder

        arg_list = join_arguments([
            '-C "{}"'.format(build_dir),
            args_to_string(args),
            args_to_string(targets)
        ])
        self._run('ninja {}'.format(arg_list))

    def _run_meson_command(self, subcommand, args=None):
        args = args or []

        build_dir = self.build_dir or self._conanfile.build_folder

        arg_list = join_arguments([
            subcommand,
            '-C "{}"'.format(build_dir),
            args_to_string(args)
        ])
        self._run('meson {}'.format(arg_list))
