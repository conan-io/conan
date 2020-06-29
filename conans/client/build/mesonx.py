import os
import platform
import sys
if sys.version_info[0] == 3 and sys.version_info[1] >= 5:
    from configparser import ConfigParser
    from pathlib import Path

from conans.client import tools
from conans.client.build import defs_to_string, join_arguments
from conans.client.build.cppstd_flags import cppstd_from_settings
from conans.client.toolchain.meson import MesonMachineFile, MesonToolchain, MesonDefaultToolchain
from conans.client.tools.env import environment_append, _environment_add, no_op
from conans.client.tools.oss import args_to_string
from conans.errors import ConanException
from conans.model.build_info import DEFAULT_BIN, DEFAULT_INCLUDE, DEFAULT_LIB
from conans.model.version import Version
from conans.util.files import decode_text, get_abs_path, mkdir
from conans.util.runners import version_runner

# Differences from stock Meson integration:
# - does not override 'default_library' if no 'shared' options was set
# - saves `build_subdir` in __init__
# - cleaned up interface: removed old arguments, removed build_dir and etc
# - added machine file support
# - added machine file generation for `toolchain`
# - backend-agnostic meson methods are used by default with ninja as a fallback for older meson versions.
# - env variables with dependency search paths are not appended when executing meson commands
# - requires pkg-config generator
# - install_folder is always added to pkg-config search paths now (since pc generator is required now)

# TODO:
# - add pkg_config_path to configure properly (cross scenario and native) or move it to machine file generation
# - fix env variables reading for native\cross once it's possible (i.e when <https://github.com/conan-io/conan/issues/7091> is fixed)
# - cleanup comments
# - add tests

# Questions:
# - Should we keep `cross-file`/`native-file` kwarg or should they be moved to `options` instead?
# - Same q as ^ for pkg-config-paths
# - How should the user extend `_get_cpu_family_and_endianness_from_arch` in case he has a custom unknown arch?
# - Should we generate machine files in dump() or in __init__()?
# - Move `MesonDefaultToolchainGenerator` to `MesonDefaultToolchain`?

class MesonX(object):
    def __init__(self, conanfile, build_subdir = None, backend = None, append_vcvars = False):
        if self.get_version() < '0.42.0':
            raise ConanException('`meson` is too old: minimum required version `0.42.0` vs current version `{}`'.format(self.get_version()))
        if not 'pkg_config' in conanfile.generators:
            raise ConanException('`pkg_config` generator is required for `meson` integration')

        self._conanfile = conanfile
        self._settings = conanfile.settings
        self._append_vcvars = append_vcvars
        self._build_subdir = build_subdir
        self._build_type = self._ss('build_type')

        # Needed for internal checks
        self._compiler = self._ss('compiler')

        # Cache version value for future use
        self._version = self.get_version()

        # Meson recommends to use ninja by default
        self.backend = backend or 'ninja'

    @staticmethod
    def get_version():
        try:
            out = version_runner(['meson', '--version'])
            version_line = decode_text(out).split('\n', 1)[0]
            version_str = version_line.rsplit(' ', 1)[-1]
            return Version(version_str)
        except Exception as e:
            raise ConanException('Error retrieving Meson version: `{}`'.format(e))

    def configure(self, source_subdir=None, build_type=None, pkg_config_paths=None, native_files=None, cross_files=None, options=None, args=None):
        if not self._conanfile.should_configure:
            return

        args = args or []
        options = options or []
        native_files = native_files or []
        cross_files = cross_files or []

        # FIXME: should we check this at all?
        if self.is_configured() and '--wipe' not in args:
            pass

        def check_arg_not_in_opts_or_args(arg_name, use_instead_msg):
            if arg_name in options:
                raise ConanException('Don\'t pass `{}` via `options`: {}'.format(arg_name, use_instead_msg))
            if any(map(lambda a: a.startswith('--{}'.format(arg_name)) or a.startswith('-D{}'.format(arg_name)), args)):
                raise ConanException('Don\'t pass `{}` via `args`: {}'.format(arg_name, use_instead_msg))

        # FIXME: meson forbids in-source builds: should we do smth about it?
        source_dir, build_dir = self._get_resolved_dirs(source_subdir)
        mkdir(build_dir)

        resolved_options = self._get_default_options()
        # overwrite default values with user's inputs
        resolved_options.update(options)

        check_arg_not_in_opts_or_args('backend', 'use `backend` kwarg in the class constructor instead')

        check_arg_not_in_opts_or_args('buildtype', 'use `build_type` kwarg instead')
        settings_build_type = self._settings.get_safe('build_type')
        if build_type and build_type != settings_build_type:
            self._conanfile.output.warn(
                'Set build type "{}" is different than the settings build_type "{}"'.format(build_type, settings_build_type))
        resolved_build_type = build_type or settings_build_type
        if resolved_build_type:
            resolved_options.update({'buildtype': '{}'.format(self._get_meson_buildtype(resolved_build_type))})

        check_arg_not_in_opts_or_args('pkg_config_path', 'use `pkg_config_paths` kwarg instead')
        pc_paths = [self._conanfile.install_folder]
        if pkg_config_paths:
            pc_paths += pkg_config_paths
        resolved_options.update({'pkg_config_path': '{}'.format(os.pathsep.join(pc_paths))})

        check_arg_not_in_opts_or_args('native-file', 'use `native_files` kwarg instead')
        check_arg_not_in_opts_or_args('cross-file', 'use `cross_files` kwarg instead')
        resolved_native_files = self._get_default_machine_files(Path(build_dir) / MesonToolchain.native_file_subdir) + native_files
        resolved_cross_files = self._get_default_machine_files(Path(build_dir) / MesonToolchain.cross_file_subdir) + cross_files
        if resolved_native_files:
            args = ['--native-file={}'.format(f) for f in resolved_native_files] + args
        if resolved_cross_files:
            args = ['--cross-file={}'.format(f) for f in resolved_cross_files] + args
        if not resolved_native_files and not resolved_cross_files:
            self._conanfile.output.warn('No machine files were generated or supplied. Using a system compiler instead.')

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
            self._run('meson setup "{}" "{}" {}'.format(source_dir, build_dir, arg_list))

    def build(self, args=None, targets=None):
        if not self._conanfile.should_build:
            return

        args = args or []
        targets = targets or []

        # FIXME: remove this check and the block below once <https://github.com/mesonbuild/meson/issues/6740> is merged.
        # Update version if necessary
        if targets:
            raise ConanException('Targets are not supported by `meson compile` yet')

        # minimum_version = '0.55.0' if targets else '0.54.0'
        # if self._version >= minimum_version:
        #     self._run_meson_command(subcommand='compile', args=targets + args)

        minimum_version = '0.54.0'
        if self._version >= minimum_version:
            self._run_meson_command(subcommand='compile', args=args)
        else:
            self._validate_ninja_usage_and_warn_agnostic_method_unavailable(minimum_version)
            meson_target = next( (t for t in targets if ':' in t), None)
            if meson_target:
                raise ConanException('Your targets contain meson syntax which is not supported by ninja: `{}`'.format(meson_target))
            self._run_ninja_targets(targets=targets,
                                    args=self._filter_non_ninja_args(args=args,
                                                                     ninja_args=['-j*', '-l*']))

    def install(self, args=None):
        if not self._conanfile.should_install:
            return

        args = args or []

        minimum_version = '0.47.0'
        if self._version >= minimum_version:
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

    def is_configured(self):
        _, build_dir = self._get_resolved_dirs()
        if self._version >= '0.50.0':
            return (Path(build_dir) / 'meson-info' / 'meson-info.json').exists()
        else:
            return (Path(build_dir) / 'meson-private' / 'coredata.dat').exists()

    def _ss(self, setname):
        """safe setting"""
        return self._conanfile.settings.get_safe(setname)

    def _so(self, setname):
        """safe option"""
        return self._conanfile.options.get_safe(setname)

    def _validate_ninja_usage_and_warn_agnostic_method_unavailable(self, minimum_version):
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

    def _get_resolved_dirs(self, source_subdir=None):
        """
        Returns (resolved_source_dir, resolved_build_dir)
        """
        source_dir = self._conanfile.source_folder
        if source_subdir:
            source_dir = str(Path(self._conanfile.source_folder) / source_subdir)

        build_dir = self._conanfile.build_folder
        if self._build_subdir:
            build_dir = str(Path(self._conanfile.build_folder) / _build_subdir)
        return (source_dir, build_dir)

    def _get_default_options(self):
        options = dict()
        if self._conanfile.package_folder:
            options['prefix'] = self._conanfile.package_folder
        options['libdir'] = DEFAULT_LIB
        options['bindir'] = DEFAULT_BIN
        options['sbindir'] = DEFAULT_BIN
        options['libexecdir'] = DEFAULT_BIN
        options['includedir'] = DEFAULT_INCLUDE

        cppstd = cppstd_from_settings(self._conanfile.settings)
        if cppstd != None:
            options['cpp_std'] = self._get_meson_cppstd(cppstd)

        shared = self._so('shared')
        if shared != None:
            options['default_library'] = 'shared' if shared else 'static'

        host_os = self._ss('os')
        if host_os and 'Windows' in host_os:
            self._conanfile.output.warn("Toolchain: Ignoring fPIC option defined for Windows")
        else:
            fpic = self._so('fPIC')
            if fpic != None:
                shared = self._so('shared')
                options['b_staticpic'] = fpic or shared

        options['b_ndebug'] = 'if-release'
        options['backend'] = self.backend

        return options

    @staticmethod
    def _get_default_machine_files(machine_files_dir):
        machine_files_path = Path(machine_files_dir)
        return list(machine_files_path.glob('*')) if machine_files_path.exists() else []

    @staticmethod
    def _options_to_string(options):
        return ' '.join([MesonX._option_to_string(k, v) for k, v in options.items()])

    @staticmethod
    def _option_to_string(key, value):
        if isinstance(value, list):
            # "-Doption=['a,1', 'b']"
            return '"-D{}={}"'.format(key, ', '.join(['\'{}\''.format(v) for v in value]))
        else:
            return '-D{}="{}"'.format(key, value)

    @staticmethod
    def _get_meson_cppstd(cppstd):
        cppstd_conan2meson = {
            '98': 'c++03', 'gnu98': 'gnu++03',
            '11': 'c++11', 'gnu11': 'gnu++11',
            '14': 'c++14', 'gnu14': 'gnu++14',
            '17': 'c++17', 'gnu17': 'gnu++17',
            '20': 'c++1z', 'gnu20': 'gnu++1z'
        }
        if cppstd not in cppstd_conan2meson:
            raise ConanException('Unknown cppstd: {}'.format(cppstd))
        return cppstd_conan2meson[cppstd]

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
            raise ConanException('Internal error: this command should not be invoked on non-`ninja` backend')

        targets = targets or []
        args = args or []

        _, build_dir = self._get_resolved_dirs()

        arg_list = join_arguments([
            '-C "{}"'.format(build_dir),
            args_to_string(args),
            args_to_string(targets)
        ])
        self._run('ninja {}'.format(arg_list))

    def _run_meson_command(self, subcommand, args=None):
        args = args or []

        _, build_dir = self._get_resolved_dirs()

        arg_list = join_arguments([
            subcommand,
            '-C "{}"'.format(build_dir),
            args_to_string(args)
        ])
        self._run('meson {}'.format(arg_list))
