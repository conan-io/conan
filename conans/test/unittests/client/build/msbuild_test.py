import os
import platform
import re
import unittest

import mock
import six
from parameterized import parameterized

from conans.client import tools
from conans.client.tools.files import chdir
from conans.client.build.msbuild import MSBuild
from conans.errors import ConanException
from conans.model.version import Version
from conans.test.utils.conanfile import MockConanfile, MockSettings


class MSBuildTest(unittest.TestCase):

    def dont_mess_with_build_type_test(self):
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

    def without_runtime_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        template = msbuild._get_props_file_contents()
        self.assertNotIn("<RuntimeLibrary>", template)

    def custom_properties_test(self):
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
    def binary_logging_on_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", output_binary_log=True)
        self.assertIn("/bl", command)

    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def binary_logging_on_with_filename_test(self):
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

    def binary_logging_off_explicit_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln", output_binary_log=False)
        self.assertNotIn("/bl", command)

    def binary_logging_off_implicit_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("dummy.sln")
        self.assertNotIn("/bl", command)

    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    @mock.patch("conans.client.build.msbuild.MSBuild.get_version")
    def binary_logging_not_supported_test(self, mock_get_version):
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

    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def get_version_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        version = MSBuild.get_version(settings)
        six.assertRegex(self, version, "(\d+\.){2,3}\d+")
        self.assertGreater(version, "15.1")

    @parameterized.expand([("16", "v142"),
                           ("15", "v141"),
                           ("14", "v140"),
                           ("12", "v120"),
                           ("11", "v110"),
                           ("10", "v100"),
                           ("9", "v90"),
                           ("8", "v80")])
    def default_toolset_test(self, compiler_version, expected_toolset):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": compiler_version,
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln")
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)

    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def skip_toolset_test(self):
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
    def explicit_toolset_test(self, expected_toolset):
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
    def custom_toolset_test(self, compiler_version, expected_toolset):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": compiler_version,
                                 "compiler.toolset": expected_toolset,
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("project_should_flags_test_file.sln")
        self.assertIn('/p:PlatformToolset="%s"' % expected_toolset, command)

    def definitions_test(self):
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

    def definitions_no_value_test(self):
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

    def verbosity_default_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("projecshould_flags_testt_file.sln")
        self.assertIn('/verbosity:minimal', command)

    def verbosity_env_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        with tools.environment_append({"CONAN_MSBUILD_VERBOSITY": "detailed"}):
            conanfile = MockConanfile(settings)
            msbuild = MSBuild(conanfile)
            command = msbuild.get_command("projecshould_flags_testt_file.sln")
            self.assertIn('/verbosity:detailed', command)

    def verbosity_explicit_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        command = msbuild.get_command("projecshould_flags_testt_file.sln", verbosity="quiet")
        self.assertIn('/verbosity:quiet', command)

    def properties_injection_test(self):
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

    def windows_ce_test(self):
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
