import os
import platform
from pathlib import Path
from configparser import ConfigParser

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.cppstd_flags import cppstd_from_settings
from conans.client.tools.env import environment_append, _environment_add
from conans.client.tools.oss import args_to_string
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB
from conans.model.version import Version
from conans.util.files import decode_text, get_abs_path, mkdir
from conans.util.runners import version_runner

# TODO:
# - add pkg_config_path to configure (cross scenario and native)
# - fix env variables reading for native\cross
# - add proper versions to meson checks

class MesonMachineFile:
    def __init__(self,
                 name,
                 path = None,
                 config: ConfigParser = None):
        if not name:
            raise ConanException("`name` is empty: machine file must have a unique name supplied")
        self.name = name

        if path and config:
            raise ConanException("Both `path` and `config` were supplied: only one should be used")
        if path:
            config = ConfigParser()
            config.read(path)
        options = config

    def dump(self, output: str):
        outpath = Path(output)
        if not outpath.exists:
            outpath.mkdir(parents=True)
        with open(outpath/self.name, 'w') as f:
            options.write(f)

class MesonToolchain:
    native_files = [] # Type: List[MesonMachineFile]
    cross_files = [] # Type: List[MesonMachineFile]

    def __init__(self, native_files = [], cross_files = []):
        self.native_files = native_files
        self.cross_files = cross_files

    def dump(self, output: str):
      if (native_files):
        outpath = Path(output) \ 'native'
        if not outpath.exists:
            outpath.mkdir(parents=True)
        for f in native_files:
          f.dump(outpath)
      if (cross_files):
        outpath = Path(output) \ 'cross'
        if not outpath.exists:
            outpath.mkdir(parents=True)
        for f in cross_files:
          f.dump(outpath)

class MesonDefaultToolchainGenerator(object):
    def __init__(self, conanfile):
        self._conanfile = conanfile

    def generate(self, force_cross = False) -> MesonToolchain:
        mt = MesonToolchain()
        if self._conanfile.settings_build:
            mt.native_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_native()))]
        if self._conanfile.settings_target:
            mt.cross_files += [MesonMachineFile(name='default.ini', config=self._dict_to_config(self._create_cross()))]
        if not self._conanfile.settings_build and not self._conanfile.settings_target:
            tmp_mt = self._create_machine_files_from_settings(force_cross)
            mt.native_files += tmp_mt.native_files
            mt.cross_files += tmp_mt.cross_files
        return mt

    @staticmethod
    def _dict_to_config(machine_dict: dict) -> ConfigParser:
        return ConfigParser().read_dict(self._filter_none(machine_dict))

    @staticmethod
    def _filter_undefined(config):
        return {section_name: {key: value for key, value in section.items() if value is not None}
                for section_name, section in config.items()}

    @staticmethod
    def _create_native(settings) -> dict:
        def none_if_empty(input: str):
            return input if input.strip() else None
        def env_or_for_build(input: str):
            return os.environ.get('{}_FOR_BUILD'.format(input)) or os.environ.get(input)
        def atr_or_for_build(settings, input: str):
            for_build_attr = '{}_build'.format(input)
            return settings.get_safe(for_build_attr) or settings.get_safe(input)

        # `_FOR_BUILD` logic is mirroring built-in meson environment variables handling logic
        config_template = {
            'binaries': {
                'c': env_or_for_build('CC'),
                'cpp': env_or_for_build('CXX'),
                'c_ld': env_or_for_build('LD'),
                'cpp_ld': env_or_for_build'LD'),
                'ar': env_or_for_build('AR'),
                'strip': env_or_for_build('STRIP'),
                'as': env_or_for_build('AS'),
                'ranlib': env_or_for_build('RANLIB'),
                'pkgconfig': tools.which('pkg-config')
            },
            'properties': {
                'c_args': none_if_empty(env_or_for_build('CPPFLAGS', '') + ' ' + env_or_for_build('CFLAGS', '')),
                'cpp_args': none_if_empty(env_or_for_build('CPPFLAGS', '') + ' ' + env_or_for_build('CXXFLAGS', '')),
                'c_link_args': env_or_for_build('LDFLAGS'),
                'cpp_link_args': env_or_for_build('LDFLAGS'),
            }
        }

        if atr_or_for_build('os'):
            os = atr_or_for_build('os')
            arch = atr_or_for_build('arch')
            config_template['build_machine'] = {
                'system': elf._get_system_from_os(os),
                'cpu_family': self._get_cpu_family_from_arch(arch),
                'cpu': arch,
                'endian': self._get_endian_from_arch(arch),
            }

        return config_template

    @staticmethod
    def _create_cross(settings, build_folder) -> dict:
        def none_if_empty(str):
            return str if str.strip() else None

        config_template = {
            'binaries': {
                'c': os.environ.get('CC'),
                'cpp': os.environ.get('CXX'),
                'c_ld': os.environ.get('LD'),
                'cpp_ld': os.environ.get('LD'),
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
                'needs_exe_wrapper': tools.cross_building(settings),
            },
            'host_machine': {
                'system': elf._get_system_from_os(settings.os),
                'cpu_family': self._get_cpu_family_from_arch(settings.arch),
                'cpu': settings.arch,
                'endian': self._get_endian_from_arch(settings.arch),
            }
        }

        if not config['binaries']['c'] and not config['binaries']['cpp']:
            raise ConanException(f'CC and CXX are undefined: C or C++ compiler must be defined when cross-building')

        return config_template

    @staticmethod
    def _create_machine_files_from_settings(settings, force_cross: boolean) -> MesonToolchain:
        is_cross = force_cross
        has_for_build = False

        if not is_cross:
            has_for_build = any(map(lambda e: os.environ.get(e), ['CC_FOR_BUILD', 'CXX_FOR_BUILD'])
            is_cross = has_for_build or any(map(lambda a: has_attr(settings, a), ['os_build', 'arch_build']))

        native_files = []
        if has_for_build or not is_cross:
            native_files += [MesonMachineFile(name='default.ini', config=self._create_native(settings))]

        cross_files = []
        if is_cross:
            cross_files += [MesonMachineFile(name='default.ini', config=self._create_cross(settings))]

        return MesonToolchain(native_files=native_files, cross_files=cross_files)

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
    def _get_cpu_family_from_arch(arch: str) -> str:
        """
        Converts from `conan/conans/client/conf/__init__.py` to `https://mesonbuild.com/Reference-tables.html#cpu-families`
        """
        arch_to_cpu_family = {
            'x86': 'x86',
            'x86_64': 'x86_64',
            'mips': 'mips',
            'mips64': 'mips64',
            'armv8': 'aarch64'
        }

        if (arch not in arch_to_cpu_family):
            if (arch.startswith('arm')):
                return 'arm'
            else:
                raise ConanException('Unknown arch: {}'.format(arch))

        return arch_to_cpu_family[arch]

    @staticmethod
    def _get_endian_from_arch(arch: str) -> str:
        if (arch.endswith('el') or arch.endswith('le')):
            return 'little'
        if (arch.endswith('be')):
            return 'big'
        return 'little'

class MesonX(object):
    def __init__(self, conanfile, build_dir=None, backend=None, append_vcvars=False):
        """
        :param conanfile: Conanfile instance
        :param backend: Generator name to use or none to autodetect.
               Possible values: ninja,vs,vs2010,vs2015,vs2017,vs2019,xcode
        :param build_type: Overrides default build type comming from settings
        """
        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._append_vcvars = append_vcvars

        self._build_dir = build_dir

        self._os = self._ss("os")
        self._compiler = self._ss("compiler")
        self._compiler_version = self._ss("compiler.version")
        self._build_type = self._ss("build_type")

        # Meson recommends to use ninja by default
        self.backend = backend or "ninja"

    @staticmethod
    def get_version():
        try:
            out = version_runner(["meson", "--version"])
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException("Error retrieving Meson version: '{}'".format(e))

    @property
    def build_folder(self):
        return self.build_dir

    def get_default_toolchain(self, force_cross: boolean = False) -> MesonToolchain:
        MesonDefaultToolchainGenerator(self._conanfile).generate(force_cross)

    def get_native_files(self):
        bdir = Path(self.build_dir)
        if not bdir.exists:
            raise ConanException("Build directory does not exist: `{}`".format(self.build_dir))
        if not (bdir \ 'native').exists:
            return []
        return list((bdir \ 'native').glob('*'))
        
    def get_cross_files(self):
        bdir = Path(self.build_dir)
        if not bdir.exists:
            raise ConanException("Build directory does not exist: `{}`".format(self.build_dir))
        if not (bdir \ 'cross').exists:
            return []
        return list((bdir \ 'cross').glob('*'))

    def configure(self, args=None, defs=None, build_type=None, pkg_config_paths=None, cache_build_folder=None, source_folder=None):
        if not self._conanfile.should_configure:
            return

        args = args or []
        defs = defs or {}

        options = self._get_default_options()
        # overwrite default values with user's inputs
        options.update(defs)

        if build_type and build_type != self._settings.get_safe("build_type"):
            self._conanfile.output.warn(
                'Set build type "{}" is different than the settings build_type "{}"'.format(build_type, settings_build_type))
        resolved_build_type = build_type or self._settings.get_safe("build_type")

        source_dir, self.build_dir = self._get_dirs(source_folder, build_folder, cache_build_folder)

        if pkg_config_paths:
            pc_paths = os.pathsep.join(get_abs_path(f, self._conanfile.install_folder)
                                       for f in pkg_config_paths)
        else:
            pc_paths = self._conanfile.install_folder

        mkdir(self.build_dir)

        arg_list = join_arguments([
            "--backend={}".format(self.backend),
            "--buildtype={}".format(resolved_build_type) if resolved_build_type else None,
            defs_to_string(options),
            args_to_string(args),
        ])
        command = 'meson setup "{}" "{}" {}'.format(source_dir, self.build_dir, arg_list)
        with environment_append({"PKG_CONFIG_PATH": pc_paths}):
            self._run(command)

    def build(self, args=None, targets=None):
        if not self._conanfile.should_build:
            return

        minimum_meson_version = '0.60.0' if targets else '0.50.0'
        if self._can_use_meson_method(minimum_meson_version):
            combined_args = (args or []) + (targets or [])
            self._run_meson_command(subcommand='compile', args=combined_args)
        else:
            if self.backend != 'ninja':
                self._raise_not_supported_with_meson_and_ninja(minimum_meson_version)
            self._run_ninja_targets(targets=targets, args=args)

    def install(self, args=None):
        if not self._conanfile.should_install:
            return

        if self._can_use_meson_method('0.50.0'):
            self._run_meson_command(subcommand='install', args=args)
        else:
            if self.backend != 'ninja':
                self._raise_not_supported_with_meson_and_ninja(minimum_meson_version)
            self._run_ninja_targets(targets=['install'], args=args)

    def test(self, args=None):
        if not self._conanfile.should_test:
            return

        if self._can_use_meson_method('0.50.0'):
            self._run_meson_command(subcommand='test', args=args)
        else:
            if self.backend != 'ninja':
                self._raise_not_supported_with_meson_and_ninja(minimum_meson_version)
            self._run_ninja_targets(targets=['test'], args=args)

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _so(self, setname):
        """safe option"""
        return self._conanfile.options.get_safe(setname)

    @staticmethod
    def _can_use_meson_method(minimum_version: str):
        return self.get_version() >= minimum_version
        
        
    @staticmethod
    def _raise_not_supported_with_meson_and_ninja(minimum_version: str):
        raise ConanException("This method is not implemented yet for `{}` backend. Change your backend to `ninja` or update your `meson`. Minimum required `meson` version is {}".format(self.backend, minimum_version))

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

        # C++ standard
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

        # shared
        shared = self._so("shared")
        if shared != None:
            options['default_library'] = shared

        # fpic
        if self._os and "Windows" not in self._os:
            fpic = self._so("fPIC")
            if fpic != None:
                shared = self._so("shared")
                options['b_staticpic'] = fpic or shared

        return options

    @staticmethod
    def _get_meson_buildtype(build_type):
        build_types = {"RelWithDebInfo": "debugoptimized",
                       "MinSizeRel": "release",
                       "Debug": "debug",
                       "Release": "release"}
        if build_type not in build_types:
            raise ConanException("Unknown build type: {}".format(build_type))
        return build_types[build_type]

    @property
    def _vcvars_needed(self):
        return (self._compiler == "Visual Studio" and self.backend == "ninja" and
                platform.system() == "Windows")

    def _run(self, command):
        if self._vcvars_needed:
            vcvars_dict = tools.vcvars_dict(self._settings, output=self._conanfile.output)
            with _environment_add(vcvars_dict, post=self._append_vcvars):
                self._conanfile.run(command)
        else:
            self._conanfile.run(command)

    def _run_ninja_targets(self, args=None, targets=None):
        if self.backend != "ninja":
            raise ConanException("Internal error: this command should not be invoked non-'ninja' backend")

        args = args or []
        build_dir = self.build_dir or self._conanfile.build_folder

        arg_list = join_arguments([
            '-C "{}"'.format(build_dir),
            args_to_string(args),
            args_to_string(targets)
        ])
        self._run("ninja {}".format(arg_list))

    def _run_meson_command(self, subcommand=None, args=None):
        args = args or []
        build_dir = self.build_dir or self._conanfile.build_folder

        arg_list = join_arguments([
            subcommand,
            '-C "()"'.format(build_dir),
            args_to_string(args)
        ])
        self._run("meson {}".format(arg_list))
