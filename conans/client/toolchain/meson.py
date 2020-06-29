import os
import platform
import sys
if sys.version_info[0] == 3 and sys.version_info[1] >= 5:
    from configparser import ConfigParser
    from pathlib import Path

from conans.client import tools
from conans.errors import ConanException
from conans.util.files import mkdir

class MesonMachineFile(object):
    """
    A wrapper for meson machine files for the use in `MesonToolchain`.
    Note: Meson requires that all ini values are quoted. E.g. `name = 'value'`
    """
    def __init__(self, name, path = None, config = None):
        if not name:
            raise ConanException('`name` is empty: machine file must have a unique name supplied')
        self.name = name

        if path and config:
            raise ConanException('Both `path` and `config` were supplied: only one should be used')
        if path:
            config = ConfigParser()
            config.read(path)
        self.options = config

    def dump(self, install_dir):
        outpath = Path(install_dir)
        if not outpath.exists():
            outpath.mkdir(parents=True)
        with open(outpath/self.name, 'w') as f:
            self.options.write(f)

class MesonToolchain(object):
    """
    A wrapper for `MesonMachineFile` for the use in `ConanFile.toolchain()`.
    Uses only supplied machine files and does *not* generate any files by itself.
    """
    native_file_subdir = 'native'
    cross_file_subdir = 'cross'

    def __init__(self, native_files = None, cross_files = None):
        self.native_files = native_files or []
        self.cross_files = cross_files or []

    def __iter__(self):
        for i in [self.native_files, self.cross_files]:
            yield i

    def dump(self, install_dir):
        def dump_files(files, outpath):
            if not files:
                pass
            if not outpath.exists():
                outpath.mkdir(parents=True)
            for f in files:
                f.dump(outpath)

        dump_files(self.native_files, Path(install_dir) / self.native_file_subdir)
        dump_files(self.cross_files, Path(install_dir) / self.cross_file_subdir)

class MesonDefaultToolchain(MesonToolchain):
    """
    A wrapper for `MesonMachineFile` for the use in `ConanFile.toolchain()`.
    Generates default machine files.
    """
    def __init__(self, conanfile, force_cross=False):
        mt_gen = MesonDefaultToolchainGenerator(conanfile)
        native_files, cross_files = mt_gen.generate(force_cross)
        super(MesonDefaultToolchain, self).__init__(native_files, cross_files)

class MesonDefaultToolchainGenerator(object):
    """
    Generates machine files from conan profiles
    """
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self, force_cross = False):
        mt = MesonToolchain()
        has_settings_build = hasattr(self._conanfile, 'settings_build') and self._conanfile.settings_build
        has_settings_target = hasattr(self._conanfile, 'settings_target') and self._conanfile.settings_target
        ## Uncomment once  <https://github.com/conan-io/conan/issues/7091> is fixed
        # if has_settings_build:
        #    mt.native_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_native(self._conanfile.settings_build, True)))]
        if has_settings_target:
            mt.cross_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_cross(self._conanfile.settings_target)))]
        if not has_settings_build and not has_settings_target:
            tmp_native_files, tmp_cross_files = self._create_machine_files_from_settings(self._conanfile.settings, force_cross)
            mt.native_files += tmp_native_files
            mt.cross_files += tmp_cross_files
        return mt

    def _dict_to_config(self, machine_dict):
        config = ConfigParser()
        config.read_dict(self._to_ini(machine_dict))
        return config

    def _to_ini(self, config):
        """
        Fixes `config` to be compatible with meson machine file format.
        """
        return {
            section_name: {
                key: self._to_ini_value(value) for key, value in section.items() if value is not None
            } for section_name, section in config.items()
        }

    def _to_ini_value(self, value):
        """
        Fixes value to be compatible with meson machine file format:
        meson requires all values to be quoted. E.g. `name = 'value'`.
        """
        if isinstance(value, bool):
            return str(value).lower()
        if isinstance(value, str):
            return "'{}'".format(value)
        return value

    def _create_native(self, settings, is_separate_profile):        
        """
        Parameters:
            is_separate_profile: true, if machine file is generated from a separate conan profile 
                                 (`--profile=native` or `--profile:build=native`);
                                 false, if generated from a common profile during a cross build (`--profile=cross`)
        
        Uses `ENV_FOR_BUILD` and `settings.*_build` if `is_separate_profile` is true 
        and `ENV` and `settings.*` otherwise.
        """

        # FIXME: Rewrite this once <https://github.com/conan-io/conan/issues/7091> is fixed
        def none_if_empty(input):
            stripped_input = input.strip()
            return stripped_input if stripped_input else None
        def env_or_for_build(input, is_separate_profile, default_val = None):
            if is_separate_profile:
                return os.environ.get(input, default_val)
            else:
                return os.environ.get('{}_FOR_BUILD'.format(input), default_val)
        def atr_or_for_build(settings, input, is_separate_profile):
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
                'pkgconfig': tools.which('pkg-config') # FIXME: See below
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

    def _create_cross(self, settings):
        def none_if_empty(input):
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
                'pkgconfig': tools.which('pkg-config') # FIXME: Do we need this at all? Is possible for `pkg-config` to be different than a system one?
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
            self._conanfile.output.warn('CC and CXX are undefined. Using a system compiler instead.')
            divined_c_compiler = tools.which('gcc') or tools.which('cc') 
            divined_cpp_compiler = tools.which('g++') or tools.which('c++') 
            if not divined_c_compiler and not divined_cpp_compiler:
                raise ConanException('Failed to divine system compiler.')
            if divined_c_compiler:
                config_template['binaries']['c'] = divined_c_compiler
            if divined_cpp_compiler:
                config_template['binaries']['cpp'] = divined_cpp_compiler

        return config_template

    def _create_machine_files_from_settings(self, settings, force_cross):
        is_cross = tools.cross_building(settings) or force_cross
        has_for_build = False

        if not is_cross:
            has_for_build = any(map(lambda e: os.environ.get(e), ['CC_FOR_BUILD', 'CXX_FOR_BUILD']))
            is_cross = has_for_build

        native_files = []
        if has_for_build or not is_cross:
            is_separate_profile = not is_cross
            native_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_native(settings, is_separate_profile)))]

        cross_files = []
        if is_cross:
            cross_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_cross(settings)))]

        return (native_files, cross_files)

    @staticmethod
    def _get_system_from_os(os):
        """
        Converts from `conan/conans/client/conf/__init__.py` to `https://mesonbuild.com/Reference-tables.html#operating-system-names`
        """
        os = os.lower()
        if (os == 'macos' or os == 'ios'):
            return 'darwin'
        else:
            return os

    @staticmethod
    def _get_cpu_family_and_endianness_from_arch(arch):
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
