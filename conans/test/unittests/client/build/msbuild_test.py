import os
import platform
import re
import unittest

import mock
import pytest
import six
from parameterized import parameterized

from conans.client import tools
from conans.client.tools.files import chdir
from conans.client.build.msbuild import MSBuild
from conans.errors import ConanException
from conans.model.version import Version
from conans.test.utils.mocks import MockSettings, MockConanfile, ConanFileMock
from conans.test.utils.test_files import temp_folder


class MSBuildTest(unittest.TestCase):

    def test_dont_mess_with_build_type(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        self.assertEqual(msbuild.build_env.flags, [])
        template = msbuild._get_props_file_contents()

        self.assertNotIn("-Ob0", template)
        self.assertNotIn("-Od", template)

        msbuild.build_env.flags = ["-Zi"]
        template = msbuild._get_props_file_contents()

        self.assertNotIn("-Ob0", template)
        self.assertNotIn("-Od", template)
        self.assertIn("-Zi", template)
        self.assertIn("<RuntimeLibrary>MultiThreadedDebugDLL</RuntimeLibrary>", template)

    def test_skip_only_none_definitions(self):
        # https://github.com/conan-io/conan/issues/6728
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        template = msbuild._get_props_file_contents(definitions={"foo": 0, "bar": False})
        self.assertIn("<PreprocessorDefinitions>foo=0;bar=False;%(PreprocessorDefinitions)",
                      template)

    def test_without_runtime(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        template = msbuild._get_props_file_contents()
        self.assertNotIn("<RuntimeLibrary>", template)

    def test_custom_properties(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_file.sln", properties={"MyProp1": "MyValue1",
                                                                      "MyProp2": "MyValue2"})
        self.assertIn('/p:MyProp1="MyValue1"', command)
        self.assertIn('/p:MyProp2="MyValue2"', command)

    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    @pytest.mark.tool_visual_studio
    def test_binary_logging_on(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", output_binary_log=True)
        self.assertIn("/bl", command)

    @pytest.mark.tool_visual_studio
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def test_binary_logging_on_with_filename(self):
        bl_filename = "a_special_log.log"
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", output_binary_log=bl_filename)
        expected_command = '/bl:"%s"' % bl_filename
        self.assertIn(expected_command, command)

    def test_binary_logging_off_explicit(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", output_binary_log=False)
        self.assertNotIn("/bl", command)

    def test_binary_logging_off_implicit(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln")
        self.assertNotIn("/bl", command)

    @pytest.mark.tool_visual_studio
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    @mock.patch("conans.client.build.msbuild.MSBuildHelper.get_version")
    def test_binary_logging_not_supported(self, mock_get_version):
        mock_get_version.return_value = Version("14")

        mocked_settings = MockSettings({"build_type": "Debug",
                                        "compiler": "Visual Studio",
                                        "compiler.version": "15",
                                        "arch": "x86_64",
                                        "compiler.runtime": "MDd"})
        conanfile = MockConanfile(mocked_settings)
        except_text = "MSBuild version detected (14) does not support 'output_binary_log' ('/bl')"
        msbuild = MSBuild(conanfile)

        with self.assertRaises(ConanException) as exc:
            msbuild.get_command("dummy.sln", output_binary_log=True)
        self.assertIn(except_text, str(exc.exception))

    def error_targets_argument_Test(self):
        conanfile = MockConanfile(MockSettings({}))
        msbuild = MSBuild(conanfile)
        with self.assertRaises(TypeError):
            msbuild.get_command("dummy.sln", targets="sometarget")

    @pytest.mark.tool_visual_studio
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def test_get_version(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        version = MSBuild.get_version(settings)
        six.assertRegex(self, version, r"(\d+\.){2,3}\d+")
        self.assertGreater(version, "15.1")

    @parameterized.expand([("16", "v142"),
                           ("15", "v141"),
                           ("14", "v140"),
                           ("12", "v120"),
                           ("11", "v110"),
                           ("10", "v100"),
                           ("9", "v90"),
                           ("8", "v80")])
    def test_default_toolset(self, compiler_version, expected_toolset):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": compiler_version,
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln")
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)

    @pytest.mark.tool_visual_studio
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def test_skip_toolset(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64"})

        class Runner(object):

            def __init__(self):
                self.commands = []

            def __call__(self, *args, **kwargs):
                self.commands.append(args[0])

        with chdir(tools.mkdir_tmp()):
            runner = Runner()
            conanfile = MockConanfile(settings, runner=runner)
            msbuild = MSBuild(conanfile)
            msbuild.build("myproject", toolset=False)
            self.assertEqual(len(runner.commands), 1)
            self.assertNotIn("PlatformToolset", runner.commands[0])

            runner = Runner()
            conanfile = MockConanfile(settings, runner=runner)
            msbuild = MSBuild(conanfile)
            msbuild.build("myproject", toolset="mytoolset")
            self.assertEqual(len(runner.commands), 1)
            self.assertIn('/p:PlatformToolset="mytoolset"', runner.commands[0])

    @parameterized.expand([("v142",),
                           ("v141",),
                           ("v140",),
                           ("v120",),
                           ("v110",),
                           ("v100",),
                           ("v90",),
                           ("v80",)])
    def test_explicit_toolset(self, expected_toolset):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln", toolset=expected_toolset)
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)

    @parameterized.expand([("16", "v141_xp"),
                           ("15", "v141_xp"),
                           ("14", "v140_xp"),
                           ("12", "v120_xp"),
                           ("11", "v110_xp")])
    def test_custom_toolset(self, compiler_version, expected_toolset):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": compiler_version,
                                 "compiler.toolset": expected_toolset,
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln")
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)

    def test_definitions(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        template = msbuild._get_props_file_contents(definitions={'_WIN32_WINNT': "0x0501"})

        self.assertIn("<PreprocessorDefinitions>"
                      "_WIN32_WINNT=0x0501;"
                      "%(PreprocessorDefinitions)</PreprocessorDefinitions>", template)

    def test_definitions_no_value(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        template = msbuild._get_props_file_contents(definitions={'_DEBUG': None})

        self.assertIn("<PreprocessorDefinitions>"
                      "_DEBUG;"
                      "%(PreprocessorDefinitions)</PreprocessorDefinitions>", template)

    def test_verbosity_default(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("projecshould_flags_testt_file.sln")
        self.assertIn('/verbosity:minimal', command)

    def test_verbosity_env(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        with tools.environment_append({"CONAN_MSBUILD_VERBOSITY": "detailed"}):
            conanfile = MockConanfile(settings)
            msbuild = MSBuild(conanfile)
            command = msbuild.get_command("projecshould_flags_testt_file.sln")
            self.assertIn('/verbosity:detailed', command)

    def test_verbosity_explicit(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("projecshould_flags_testt_file.sln", verbosity="quiet")
        self.assertIn('/verbosity:quiet', command)

    def test_properties_injection(self):
        # https://github.com/conan-io/conan/issues/4471
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", props_file_path="conan_build.props")

        match = re.search('/p:ForceImportBeforeCppTargets="(.+?)"', command)
        self.assertTrue(
            match, "Haven't been able to find the ForceImportBeforeCppTargets")

        props_file_path = match.group(1)
        self.assertTrue(os.path.isabs(props_file_path))
        self.assertEqual(os.path.basename(props_file_path), "conan_build.props")

    def test_windows_ce(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "9",
                                 "os": "WindowsCE",
                                 "os.platform": "YOUR PLATFORM SDK (ARMV4)",
                                 "arch": "armv4"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("test.sln")
        self.assertIn('/p:Platform="YOUR PLATFORM SDK (ARMV4)"', command)

    @unittest.skipUnless(platform.system() == "Windows", "Requires Visual Studio installation path")
    def test_arch_override(self):
        settings = MockSettings({"build_type": "Release",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "compiler.runtime": "MDd",
                                 "os": "Windows",
                                 "arch": "x86_64"})
        conanfile = ConanFileMock()
        conanfile.settings = settings
        props_file_path = os.path.join(temp_folder(), "conan_build.props")

        msbuild = MSBuild(conanfile)
        msbuild.build("project_file.sln", property_file_name=props_file_path)
        self.assertIn("vcvarsall.bat\" amd64", conanfile.command)
        self.assertIn("/p:Platform=\"x64\"", conanfile.command)
        msbuild.build("project_file.sln", arch="x86", property_file_name=props_file_path)
        self.assertIn("vcvarsall.bat\" x86", conanfile.command)
        self.assertIn("/p:Platform=\"x86\"", conanfile.command)

    def test_intel(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "intel",
                                 "compiler.version": "19.1",
                                 "compiler.base": "Visual Studio",
                                 "compiler.base.version": "15",
                                 "arch": "x86_64"})
        expected_toolset = "Intel C++ Compiler 19.1"
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln")
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)
