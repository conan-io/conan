import unittest
import tempfile
import textwrap
import os

import six

import conan.tools.qbs.qbsprofile as qbs

from conans import tools
from conans.errors import ConanException
from conans.test.utils.mocks import MockConanfile, MockSettings, MockOptions


class RunnerMock(object):
    class Expectation(object):
        def __init__(self, return_ok=True, output=None):
            self.return_ok = return_ok
            if six.PY2 and output:
                output = output.decode("utf-8")
            self.output = output

    def __init__(self, expectations=None):
        self.command_called = []
        self.expectations = expectations or [RunnerMock.Expectation()]

    def __call__(self, command, output, win_bash=False, subsystem=None):
        self.command_called.append(command)
        self.win_bash = win_bash
        self.subsystem = subsystem
        if not self.expectations:
            return 1
        expectation = self.expectations.pop(0)
        if expectation.output and output and hasattr(output, 'write'):
            output.write(expectation.output)
        return 0 if expectation.return_ok else 1


class MockConanfileWithFolders(MockConanfile):
    install_folder = tempfile.mkdtemp()

    def __del__(self):
        tools.rmdir(self.install_folder)

    def run(self, *args, **kwargs):
        if self.runner:
            if 'output' not in kwargs:
                kwargs['output'] = None
            self.runner(*args, **kwargs)


class QbsGenericTest(unittest.TestCase):
    def test_convert_bool(self):
        self.assertEqual(qbs._bool(True), 'true')
        self.assertEqual(qbs._bool(False), 'false')

    def test_convert_build_variant(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._build_variant, None)

        for build_type, build_variant in qbs._build_variant.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'os': 'Linux',
                'compiler': 'gcc',
                'build_type': build_type}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._build_variant, build_variant)

    def test_convert_architecture(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._architecture, None)

        for arch, architecture in qbs._architecture.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'os': 'Linux',
                'compiler': 'gcc',
                'arch': arch}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._architecture, architecture)

    def test_convert_optimization(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._optimization, None)

        for build_type, optimization in qbs._optimization.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'os': 'Linux',
                'compiler': 'gcc',
                'build_type': build_type}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._optimization, optimization)

    def test_use_sysroot_from_env(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc'}))

        sysroot = '/path/to/sysroot/foo/bar'
        with tools.environment_append({'SYSROOT': sysroot}):
            qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._sysroot, sysroot)

    def test_detect_fpic_from_options(self):
        f_pic = {
            True: 'true',
            False: 'false',
            None: None
        }

        for option, value in f_pic.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                    'os': 'Linux',
                    'compiler': 'gcc'
                }),
                MockOptions({
                    'fPIC': option
                }))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._position_independent_code, value)

    def test_convert_cxx_language_version(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._cxx_language_version, None)
        conanfile = MockConanfileWithFolders(MockSettings({
            'os': 'Linux',
            'compiler': 'gcc',
            'compiler.cppstd': 17}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._cxx_language_version, 'c++17')

        for cppstd, cxx_language_version in qbs._cxx_language_version.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'os': 'Linux',
                'compiler': 'gcc',
                'compiler.cppstd': cppstd}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._cxx_language_version,
                             cxx_language_version)

    def test_convert_target_platform(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'compiler': 'gcc'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._target_platform, None)

        for os, target_platform in qbs._target_platform.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'os': os,
                'compiler': 'gcc'}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._target_platform,
                             target_platform)

    def test_convert_runtime_library(self):
        conanfile = MockConanfileWithFolders(MockSettings({
            'compiler': 'Visual Studio'}))

        qbs_toolchain = qbs.QbsProfile(conanfile)
        self.assertEqual(qbs_toolchain._runtime_library, None)

        for runtime, runtime_library in qbs._runtime_library.items():
            conanfile = MockConanfileWithFolders(MockSettings({
                'compiler': 'Visual Studio',
                'compiler.runtime': runtime}))

            qbs_toolchain = qbs.QbsProfile(conanfile)
            self.assertEqual(qbs_toolchain._runtime_library,
                             runtime_library)

    def test_split_env_var_into_list(self):
        env_var_list = ['-p1', '-p2', '-p3_with_value=13',
                        '-p_with_space1="hello world"',
                        '"-p_with_space2=Hello World"']
        expected_list = ['-p1', '-p2', '-p3_with_value=13',
                         '-p_with_space1=hello world',
                         '-p_with_space2=Hello World']
        env_var = ' '.join(env_var_list)
        self.assertEqual(qbs._env_var_to_list(env_var), expected_list)

    def test_compiler_not_in_settings(self):
        conanfile = MockConanfile(MockSettings({}))
        with self.assertRaises(ConanException):
            qbs._check_for_compiler(conanfile)

    def test_compiler_in_settings_not_supported(self):
        conanfile = MockConanfile(
            MockSettings({'compiler': 'not realy a compiler name'}))
        with self.assertRaises(ConanException):
            qbs._check_for_compiler(conanfile)

    def test_valid_compiler(self):
        supported_compilers = ['Visual Studio', 'gcc', 'clang']
        for compiler in supported_compilers:
            conanfile = MockConanfile(MockSettings({'compiler': compiler}))
            qbs._check_for_compiler(conanfile)

    @staticmethod
    def _settings_to_test_against():
        return [
            {'os': 'Windows', 'compiler': 'gcc', 'compiler.version': '6', 'qbs_compiler': 'mingw'},
            {'os': 'Windows', 'compiler': 'clang', 'compiler.version': '3.9',
             'qbs_compiler': 'clang-cl'},
            {'os': 'Windows', 'compiler': 'Visual Studio', 'compiler.version': '15',
             'qbs_compiler': 'cl'},
            {'os': 'Windows', 'compiler': 'Visual Studio', 'compiler.version': '15',
             'compiler.toolset': 'ClangCL', 'qbs_compiler': 'clang-cl'},
            {'os': 'Windows', 'compiler': 'msvc', 'compiler.version': '19.0',
             'qbs_compiler': 'cl'},
            {'os': 'Linux', 'compiler': 'gcc', 'compiler.version': '6', 'qbs_compiler': 'gcc'},
            {'os': 'Linux', 'compiler': 'clang', 'compiler.version': '3.9', 'qbs_compiler': 'clang'}
        ]

    def test_convert_compiler_name_to_qbs_compiler_name(self):
        for settings in self._settings_to_test_against():
            def expected():
                return settings['qbs_compiler']
            conanfile = MockConanfile(MockSettings(settings))
            self.assertEqual(qbs._default_compiler_name(conanfile), expected())

    def test_settings_dir_location(self):
        conanfile = MockConanfileWithFolders(MockSettings({}))
        self.assertEqual(
            qbs._settings_dir(conanfile),
            '%s/conan_qbs_toolchain_settings_dir' % conanfile.install_folder)

    @unittest.skipIf(os.name == 'nt', "Test can only be performed with known MSVC version")
    def test_setup_toolchain_without_any_env_values(self):
        for settings in self._settings_to_test_against():
            conanfile = MockConanfileWithFolders(MockSettings(settings), runner=RunnerMock())
            qbs._setup_toolchains(conanfile)
            self.assertEqual(len(conanfile.runner.command_called), 1)
            self.assertEqual(
                conanfile.runner.command_called[0],
                'qbs-setup-toolchains --settings-dir "%s" %s %s' % (
                    qbs._settings_dir(conanfile), settings['qbs_compiler'],
                    qbs._profile_name))

    def test_setup_toolchain_with_compiler_from_env(self):
        compiler = 'compiler_from_env'
        for settings in self._settings_to_test_against():
            conanfile = MockConanfileWithFolders(MockSettings(settings), runner=RunnerMock())
            with tools.environment_append({'CC': compiler}):
                qbs._setup_toolchains(conanfile)
            self.assertEqual(len(conanfile.runner.command_called), 1)
            self.assertEqual(
                conanfile.runner.command_called[0],
                'qbs-setup-toolchains --settings-dir "%s" %s %s' % (
                    qbs._settings_dir(conanfile), compiler,
                    qbs._profile_name))

    def test_linker_flags_parser(self):
        test_data_ld_flags = {
            '-Wl,flag1': ([], ['flag1']),
            '-Wl,flag1,flag2': ([], ['flag1', 'flag2']),
            '-Wl,flag1 -Wl,flag2': ([], ['flag1', 'flag2']),
            '-dFlag1': (['-dFlag1'], []),
            '-dFlag1 -dFlag2': (['-dFlag1', '-dFlag2'], []),
            '-Wl,flag1 -dFlag1': (['-dFlag1'], ['flag1']),
            '-Wl,flag1,flag2 -dFlag1': (['-dFlag1'], ['flag1', 'flag2']),
            '-Wl,flag1,flag2 -dFlag1 -Wl,flag3 -dFlag2 -dFlag3 -Wl,flag4,flag5':
                (['-dFlag1', '-dFlag2', '-dFlag3'],
                 ['flag1', 'flag2', 'flag3', 'flag4', 'flag5']),
        }
        for ld_flags, expected in test_data_ld_flags.items():
            driver_linker_flags, linker_flags = expected
            parser = qbs.LinkerFlagsParser(qbs._env_var_to_list(ld_flags))
            self.assertEqual(parser.driver_linker_flags,
                             driver_linker_flags)
            self.assertEqual(parser.linker_flags,
                             linker_flags)

    @staticmethod
    def _generate_flags(flag, qbs_key):
        return {'env': ('-{0}1 -{0}2 -{0}3_with_value=13 '
                        '-{0}_with_space="hello world"').format(flag),
                'qbs_value': ("['-{0}1', '-{0}2', '-{0}3_with_value=13', "
                              "'-{0}_with_space=hello world']").format(flag),
                'qbs_key': qbs_key}

    def test_flags_from_env(self):
        asm = self._generate_flags('asm', 'assemblerFlags')
        c = self._generate_flags('c', 'cFlags')
        cpp = self._generate_flags('cpp', 'cppFlags')
        cxx = self._generate_flags('cxx', 'cxxFlags')
        wl = self._generate_flags('Wl,', 'linkerFlags')
        ld = self._generate_flags('ld', 'driverLinkerFlags')
        env = {
            'ASFLAGS': asm['env'],
            'CFLAGS': c['env'],
            'CPPFLAGS': cpp['env'],
            'CXXFLAGS': cxx['env'],
            'LDFLAGS': '%s %s' % (wl['env'], ld['env'])
        }
        with tools.environment_append(env):
            flags_from_env = qbs._flags_from_env()

        expected_flags = {
            'cpp.'+asm['qbs_key']: asm['qbs_value'],
            'cpp.'+c['qbs_key']: c['qbs_value'],
            'cpp.'+cpp['qbs_key']: cpp['qbs_value'],
            'cpp.'+cxx['qbs_key']: cxx['qbs_value'],
            'cpp.'+wl['qbs_key']: wl['qbs_value'].replace('-Wl,', ''),
            'cpp.'+ld['qbs_key']: ld['qbs_value']
        }
        self.assertEqual(flags_from_env, expected_flags)

    @staticmethod
    def _generate_qbs_config_output():
        return textwrap.dedent('''\
            profiles.conan.cpp.cCompilerName: "gcc"
            profiles.conan.cpp.compilerName: "g++"
            profiles.conan.cpp.cxxCompilerName: "g++"
            profiles.conan.cpp.driverFlags: \
            ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
            profiles.conan.cpp.platformCommonCompilerFlags: undefined
            profiles.conan.cpp.platformLinkerFlags: undefined
            profiles.conan.cpp.toolchainInstallPath: "/usr/bin"
            profiles.conan.cpp.toolchainPrefix: "arm-none-eabi-"
            profiles.conan.qbs.someBoolProp: "true"
            profiles.conan.qbs.someIntProp: "13"
            profiles.conan.qbs.toolchain: ["gcc"]
            ''')

    def test_read_qbs_toolchain_from_qbs_config_output(self):
        expected_config = {
            'cpp.cCompilerName': '"gcc"',
            'cpp.compilerName': '"g++"',
            'cpp.cxxCompilerName': '"g++"',
            'cpp.driverFlags': '["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]',
            'cpp.platformCommonCompilerFlags': 'undefined',
            'cpp.platformLinkerFlags': 'undefined',
            'cpp.toolchainInstallPath': '"/usr/bin"',
            'cpp.toolchainPrefix': '"arm-none-eabi-"',
            'qbs.someBoolProp': 'true',
            'qbs.someIntProp': '13',
            'qbs.toolchain': '["gcc"]'
        }

        conanfile = MockConanfileWithFolders(
            MockSettings({}), runner=RunnerMock(
                expectations=[RunnerMock.Expectation(
                    output=self._generate_qbs_config_output())]))
        config = qbs._read_qbs_toolchain_from_config(conanfile)
        self.assertEqual(len(conanfile.runner.command_called), 1)
        self.assertEqual(conanfile.runner.command_called[0],
                         'qbs-config --settings-dir "%s" --list' % (
                            qbs._settings_dir(conanfile)))
        self.assertEqual(config, expected_config)

    @unittest.skipIf(six.PY2, "Order of qbs output is defined only for PY3")
    def test_toolchain_content(self):
        expected_content = textwrap.dedent('''\
            import qbs

            Project {
                Profile {
                    name: "conan_toolchain_profile"

                    /* detected via qbs-setup-toolchains */
                    cpp.cCompilerName: "gcc"
                    cpp.compilerName: "g++"
                    cpp.cxxCompilerName: "g++"
                    cpp.driverFlags: ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
                    cpp.platformCommonCompilerFlags: undefined
                    cpp.platformLinkerFlags: undefined
                    cpp.toolchainInstallPath: "/usr/bin"
                    cpp.toolchainPrefix: "arm-none-eabi-"
                    qbs.someBoolProp: true
                    qbs.someIntProp: 13
                    qbs.toolchain: ["gcc"]

                    /* deduced from environment */
                    qbs.sysroot: "/foo/bar/path"

                    /* conan settings */
                    qbs.buildVariant: "release"
                    qbs.architecture: "x86_64"
                    qbs.targetPlatform: "linux"
                    qbs.optimization: "small"
                    cpp.cxxLanguageVersion: "c++17"

                    /* package options */
                    cpp.positionIndependentCode: true
                }
            }''')

        conanfile = MockConanfileWithFolders(
            MockSettings({
                'compiler': 'gcc',
                'compiler.cppstd': 17,
                'os': 'Linux',
                'build_type': 'MinSizeRel',
                'arch': 'x86_64'
            }),
            options=MockOptions({
                'fPIC': True
            }),
            runner=RunnerMock(
                expectations=[
                    RunnerMock.Expectation(),
                    RunnerMock.Expectation(
                        output=self._generate_qbs_config_output()),
                ]))

        with tools.environment_append({'SYSROOT': '/foo/bar/path'}):
            qbs_toolchain = qbs.QbsProfile(conanfile)

        self.assertEqual(qbs_toolchain.content, expected_content)

    @staticmethod
    def _generate_qbs_config_output_msvc():
        return textwrap.dedent('''\
            profiles.conan.cpp.compilerVersion: "19.28.29333"
            profiles.conan.cpp.toolchainInstallPath: \
            "C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.28.29333/bin/Hostx64/x64"
            profiles.conan.qbs.architecture: "x86_64"
            profiles.conan.qbs.targetPlatform: "windows"
            profiles.conan.qbs.toolchainType: "msvc"
            profiles.conan.cpp.driverFlags: \
            ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
            profiles.conan.qbs.someBoolProp: "true"
            profiles.conan.qbs.someIntProp: "13"
            ''')

    def test_read_qbs_toolchain_from_qbs_config_output_msvc(self):
        expected_config = {
            'cpp.compilerVersion': '"19.28.29333"',
            'cpp.toolchainInstallPath': '"C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.28.29333/bin/Hostx64/x64"',
            'qbs.architecture': '"x86_64"',
            'qbs.targetPlatform': '"windows"',
            'qbs.toolchainType': '"msvc"',
            'cpp.driverFlags': '["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]',
            'qbs.someBoolProp': 'true',
            'qbs.someIntProp': '13',
        }

        conanfile = MockConanfileWithFolders(
            MockSettings({}), runner=RunnerMock(
                expectations=[RunnerMock.Expectation(
                    output=self._generate_qbs_config_output_msvc())]))
        config = qbs._read_qbs_toolchain_from_config(conanfile)
        self.assertEqual(len(conanfile.runner.command_called), 1)
        self.assertEqual(conanfile.runner.command_called[0],
                         'qbs-config --settings-dir "%s" --list' % (
                            qbs._settings_dir(conanfile)))
        self.assertEqual(config, expected_config)

    @unittest.skipIf(six.PY2, "Order of qbs output is defined only for PY3")
    def test_toolchain_content_msvc(self):
        expected_content = textwrap.dedent('''\
            import qbs

            Project {
                Profile {
                    name: "conan_toolchain_profile"

                    /* detected via qbs-setup-toolchains */
                    cpp.compilerVersion: "19.28.29333"
                    cpp.toolchainInstallPath: "C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.28.29333/bin/Hostx64/x64"
                    qbs.architecture: "x86_64"
                    qbs.targetPlatform: "windows"
                    qbs.toolchainType: "msvc"
                    cpp.driverFlags: ["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]
                    qbs.someBoolProp: true
                    qbs.someIntProp: 13

                    /* deduced from environment */
                    qbs.sysroot: "/foo/bar/path"

                    /* conan settings */
                    qbs.buildVariant: "release"
                    qbs.optimization: "small"
                    cpp.runtimeLibrary: "dynamic"

                    /* package options */
                    cpp.positionIndependentCode: true
                }
            }''')

        conanfile = MockConanfileWithFolders(
            MockSettings({
                'compiler': 'Visual Studio',
                'compiler.version': 15,
                'compiler.runtime': 'MD',
                'os': 'Windows',
                'build_type': 'MinSizeRel',
                'arch': 'x86_64',
            }),
            options=MockOptions({
                'fPIC': True
            }),
            runner=RunnerMock(
                expectations=[
                    RunnerMock.Expectation(),
                    RunnerMock.Expectation(
                        output=self._generate_qbs_config_output_msvc()),
                ]))

        with tools.environment_append({'SYSROOT': '/foo/bar/path'}):
            qbs_toolchain = qbs.QbsProfile(conanfile)

        self.assertEqual(qbs_toolchain.content, expected_content)
