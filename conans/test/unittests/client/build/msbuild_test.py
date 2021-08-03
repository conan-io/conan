import os
import re
import unittest

from parameterized import parameterized

from conans.client import tools
from conans.client.build.msbuild import MSBuild
from conans.test.utils.mocks import MockSettings, MockConanfile


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

    def test_error_targets_argument(self):
        conanfile = MockConanfile(MockSettings({}))
        msbuild = MSBuild(conanfile)
        with self.assertRaises(TypeError):
            msbuild.get_command("dummy.sln", targets="sometarget")

    @parameterized.expand([("17", "v143"),
                           ("16", "v142"),
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

    @parameterized.expand([("v143",),
                           ("v142",),
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
