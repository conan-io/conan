import mock
import platform
import shutil
import shlex
import textwrap
import unittest

import six

from mock.mock import MagicMock, Mock
import conan.tools.microsoft as microsoft
from conan.tools.microsoft import MSBuildToolchain
from conan.tools.qbs.qbsprofile import QbsProfile, LinkerFlagsParser
from conans.errors import ConanException


class QbsProfileWithoutConstructor(QbsProfile):
    def __init__(self, conanfile):
        self._conanfile = conanfile


class QbsProfileTest(unittest.TestCase):
    def test_convert_bool(self):
        qbs_profile = QbsProfileWithoutConstructor(Mock())
        self.assertEqual(qbs_profile._bool(True), 'true')
        self.assertEqual(qbs_profile._bool(False), 'false')

    def test_construct_qbs_profile(self):
        def side_effect_settings_get_safe(setting):
            settings = {
                "arch": "x86",
                "build_type": "Debug",
                "compiler.cppstd": "17",
                "os": "Linux",
                "compiler.runtime": None,
            }
            return settings[setting]

        def side_effect_options_get_safe(option):
            options = {
                "fPIC": "True"
            }
            return options[option]

        init = QbsProfile._init

        with mock.patch.object(QbsProfile, '_init', new_callable=MagicMock()) as mock_init:
            conanfile = Mock()
            qbs_profile = QbsProfile(conanfile)
            mock_init.assert_called_once_with(conanfile)

            qbs_profile._check_for_compiler = MagicMock()
            expected_build_env = {"SYSROOT": "/path/to/sysroot"}
            qbs_profile._get_build_env = MagicMock(return_value=expected_build_env)
            qbs_profile._setup_toolchains = MagicMock()
            qbs_profile._read_qbs_profile_from_config = MagicMock(return_value="test-profile")
            qbs_profile._flags_from_env = MagicMock(return_value={"Flag1": "value1"})
            expected_settings_dir = "settings_dir"
            qbs_profile._settings_dir = MagicMock(return_value=expected_settings_dir)

            conanfile.settings.get_safe = Mock(side_effect=side_effect_settings_get_safe)
            conanfile.options.get_safe = Mock(side_effect=side_effect_options_get_safe)

            with mock.patch.object(shutil, 'rmtree', new_callable=MagicMock) as mock_rmtree:
                init(qbs_profile, conanfile)
                qbs_profile._check_for_compiler.assert_called_once_with()
                qbs_profile._get_build_env.assert_called_once_with()
                qbs_profile._setup_toolchains.assert_called_once_with(
                    expected_build_env)
                qbs_profile._read_qbs_profile_from_config.assert_called_once_with()
                self.assertEqual(qbs_profile._profile_values_from_setup,
                                 qbs_profile._read_qbs_profile_from_config.return_value)
                qbs_profile._flags_from_env.assert_called_once_with(expected_build_env)
                self.assertEqual(qbs_profile._profile_values_from_env,
                                 qbs_profile._flags_from_env.return_value)
                qbs_profile._settings_dir.assert_called_once_with()
                mock_rmtree.assert_called_once_with(expected_settings_dir)
                conanfile.settings.get_safe.assert_any_call("arch")
                self.assertEqual(qbs_profile._architecture, "x86")
                conanfile.settings.get_safe.assert_any_call("build_type")
                self.assertEqual(qbs_profile._build_variant, "debug")
                self.assertEqual(qbs_profile._optimization, None)
                conanfile.settings.get_safe.assert_any_call("compiler.cppstd")
                self.assertEqual(qbs_profile._cxx_language_version, "c++17")
                conanfile.settings.get_safe.assert_any_call("os")
                self.assertEqual(qbs_profile._target_platform, "linux")
                conanfile.settings.get_safe.assert_any_call("compiler.runtime")
                self.assertEqual(qbs_profile._runtime_library, None)
                self.assertEqual(qbs_profile._sysroot, expected_build_env["SYSROOT"])
                conanfile.options.get_safe.assert_any_call("fPIC")
                self.assertEqual(qbs_profile._position_independent_code, "true")

    def test_split_env_var_into_list(self):
        with mock.patch.object(shlex, 'split', new_callable=MagicMock) as mock_split:
            qbs_profile = QbsProfileWithoutConstructor(Mock())
            dummy = 42
            qbs_profile._env_var_to_list(dummy)
            mock_split.assert_called_once_with(dummy)

    def test_compiler_not_in_settings(self):
        conanfile = Mock()
        conanfile.settings.get_safe = MagicMock(return_value=None)
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        with self.assertRaises(ConanException):
            qbs_profile._check_for_compiler()
        conanfile.settings.get_safe.assert_called_once_with("compiler")

    def test_compiler_in_settings_not_supported(self):
        conanfile = Mock()
        conanfile.settings.get_safe = MagicMock(return_value="not realy a compiler name")
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        with self.assertRaises(ConanException):
            qbs_profile._check_for_compiler()
        conanfile.settings.get_safe.assert_called_once_with("compiler")

    def test_valid_compiler(self):
        supported_compilers = ["Visual Studio", "gcc", "clang"]
        conanfile = Mock()
        for compiler in supported_compilers:
            qbs_profile = QbsProfileWithoutConstructor(conanfile)
            conanfile.settings.get_safe = MagicMock(return_value=compiler)
            qbs_profile._check_for_compiler()
            conanfile.settings.get_safe.assert_called_once_with("compiler")

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
            def side_effect_settings_get_safe(setting_name):
                return settings[setting_name]

            def expected():
                return settings['qbs_compiler']

            conanfile = Mock()
            conanfile.settings.get_safe = Mock(side_effect=side_effect_settings_get_safe)
            with mock.patch.object(MSBuildToolchain, '_msvs_toolset',
                                   new_callable=MagicMock) as mock_msvs_toolset:
                mock_msvs_toolset.return_value = settings.get('compiler.toolset')
                qbs_profile = QbsProfileWithoutConstructor(conanfile)
                self.assertEqual(qbs_profile._default_compiler_name(), expected())

    def test_settings_dir_location(self):
        conanfile = Mock()
        conanfile.install_folder = "dummy"
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        self.assertEqual(
            qbs_profile._settings_dir(),
            '%s/conan_qbs_toolchain_settings_dir' % conanfile.install_folder)

    def test_setup_toolchain_without_any_env_values(self):
        for settings in self._settings_to_test_against():
            conanfile = Mock()
            conanfile.run = MagicMock()
            qbs_profile = QbsProfileWithoutConstructor(conanfile)
            qbs_profile._default_compiler_name = MagicMock(return_value=settings['qbs_compiler'])
            qbs_profile._settings_dir = MagicMock(return_value="/path/to/settings/dir")

            with mock.patch.object(platform, 'system',
                                   new_callable=MagicMock) as mock_platform_system:
                mock_platform_system.return_value = settings['os']
                with mock.patch.object(microsoft, 'VCVars', new_callable=MagicMock) as mock_vcvars:
                    mock_vcvars.generate = MagicMock()

                    expected_run_cmd = 'qbs-setup-toolchains --settings-dir "{}" {} {}'.format(
                        qbs_profile._settings_dir.return_value, settings['qbs_compiler'],
                        qbs_profile._profile_name)
                    expected_env = "conanvcvars" if settings['qbs_compiler'] in [
                        'cl', 'clang-cl'] else None
                    qbs_profile._setup_toolchains(dict())
                    conanfile.run.assert_called_once_with(expected_run_cmd, env=expected_env)

    def test_setup_toolchain_with_compiler_from_env(self):
        compiler = 'compiler_from_env'
        for settings in self._settings_to_test_against():
            conanfile = Mock()
            conanfile.run = MagicMock()
            qbs_profile = QbsProfileWithoutConstructor(conanfile)
            qbs_profile._settings_dir = MagicMock(return_value="/path/to/settings/dir")
            build_env = {'CC': compiler}

            with mock.patch.object(platform, 'system',
                                   new_callable=MagicMock) as mock_platform_system:
                mock_platform_system.return_value = settings['os']
                expected_run_cmd = 'qbs-setup-toolchains --settings-dir "{}" {} {}'.format(
                    qbs_profile._settings_dir.return_value, compiler,
                    qbs_profile._profile_name)
                qbs_profile._setup_toolchains(build_env)
                conanfile.run.assert_called_once_with(expected_run_cmd, env=None)

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
        qbs_profile = QbsProfileWithoutConstructor(Mock())
        for ld_flags, expected in test_data_ld_flags.items():
            driver_linker_flags, linker_flags = expected
            parser = LinkerFlagsParser(qbs_profile._env_var_to_list(ld_flags))
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

        conanfile = Mock()
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        flags_from_env = qbs_profile._flags_from_env(env)

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

        def side_effect_conanfile_run(command, output):
            del command
            output.write(self._generate_qbs_config_output())

        conanfile = Mock()
        conanfile.run = Mock(side_effect=side_effect_conanfile_run)
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        qbs_profile._settings_dir = MagicMock(return_value="/path/to/s/dir")
        config = qbs_profile._read_qbs_profile_from_config()

        conanfile.run.assert_called_once_with(
            'qbs-config --settings-dir "{}" --list'.format(
                qbs_profile._settings_dir.return_value), output=mock.ANY)
        self.assertEqual(config, expected_config)

    @unittest.skipIf(six.PY2, "Order of qbs output is defined only for PY3")
    def test_profile_content(self):
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

        qbs_profile = QbsProfileWithoutConstructor(Mock())
        qbs_profile._profile_values_from_setup = {
            "cpp.cCompilerName": '"gcc"',
            "cpp.compilerName": '"g++"',
            "cpp.cxxCompilerName": '"g++"',
            "cpp.driverFlags": '["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]',
            "cpp.platformCommonCompilerFlags": "undefined",
            "cpp.platformLinkerFlags": "undefined",
            "cpp.toolchainInstallPath": '"/usr/bin"',
            "cpp.toolchainPrefix": '"arm-none-eabi-"',
            "qbs.someBoolProp": "true",
            "qbs.someIntProp": 13,
            "qbs.toolchain": '["gcc"]'
        }
        qbs_profile._profile_values_from_env = {}
        qbs_profile._build_variant = "release"
        qbs_profile._architecture = "x86_64"
        qbs_profile._optimization = "small"
        qbs_profile._sysroot = "/foo/bar/path"
        qbs_profile._position_independent_code = "true"
        qbs_profile._cxx_language_version = "c++17"
        qbs_profile._target_platform = "linux"
        qbs_profile._runtime_library = None
        self.assertEqual(qbs_profile.content, expected_content)

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

        def side_effect_conanfile_run(command, output):
            del command
            output.write(self._generate_qbs_config_output_msvc())

        conanfile = Mock()
        conanfile.run = Mock(side_effect=side_effect_conanfile_run)
        qbs_profile = QbsProfileWithoutConstructor(conanfile)
        qbs_profile._settings_dir = MagicMock(return_value="/path/to/s/dir")
        config = qbs_profile._read_qbs_profile_from_config()

        conanfile.run.assert_called_once_with(
            'qbs-config --settings-dir "{}" --list'.format(
                qbs_profile._settings_dir.return_value), output=mock.ANY)
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

        qbs_profile = QbsProfileWithoutConstructor(Mock())
        qbs_profile._profile_values_from_setup = {
            "cpp.compilerVersion": '"19.28.29333"',
            "cpp.toolchainInstallPath": '"C:/Program Files (x86)/Microsoft Visual Studio/2019/Community/VC/Tools/MSVC/14.28.29333/bin/Hostx64/x64"',
            "qbs.architecture": '"x86_64"',
            "qbs.targetPlatform": '"windows"',
            "qbs.toolchainType": '"msvc"',
            "cpp.driverFlags": '["-march=armv7e-m", "-mtune=cortex-m4", "--specs=nosys.specs"]',
            "qbs.someBoolProp": "true",
            "qbs.someIntProp": 13
        }
        qbs_profile._profile_values_from_env = {}
        qbs_profile._build_variant = "release"
        qbs_profile._optimization = "small"
        qbs_profile._runtime_library = "dynamic"
        qbs_profile._sysroot = "/foo/bar/path"
        qbs_profile._position_independent_code = "true"
        qbs_profile._cxx_language_version = None
        qbs_profile._target_platform = None
        self.assertEqual(qbs_profile.content, expected_content)
