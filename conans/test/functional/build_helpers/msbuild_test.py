import os
import platform
import textwrap
import unittest

import pytest
import six
import mock
from parameterized import parameterized

from conans.client import tools
from conans.client.tools.files import replace_in_file
from conans.model.ref import PackageReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.test.assets.visual_project_files import get_vs_project_files
from conans.util.files import load
from conans.client.tools.files import chdir
from conans.client.build.msbuild import MSBuild
from conans.errors import ConanException
from conans.model.version import Version
from conans.test.utils.mocks import MockSettings, MockConanfile, ConanFileMock
from conans.test.utils.test_files import temp_folder


class MSBuildTest(unittest.TestCase):

    @pytest.mark.slow
    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows" or six.PY2, reason="Requires MSBuild")
    def test_build_vs_project(self):
        conan_build_vs = """
from conans import ConanFile, MSBuild

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    exports = "*"
    settings = "os", "build_type", "arch", "compiler", "cppstd"

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("MyProject.sln", verbosity="normal")

    def package(self):
        self.copy(pattern="*.exe")
"""
        client = TestClient()

        # Test cpp standard stuff

        files = get_vs_project_files(std="cpp17_2015")
        files[CONANFILE] = conan_build_vs

        client.save(files)
        client.run('create . Hello/1.2.1@lasote/stable -s cppstd=11 -s '
                   'compiler="Visual Studio" -s compiler.version=14', assert_error=True)

        client.run('create . Hello/1.2.1@lasote/stable -s cppstd=17 '
                   '-s compiler="Visual Studio" -s compiler.version=14')
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs

        # Try to not update the project
        client.cache._config = None  # Invalidate cached config

        replace_in_file(client.cache.conan_conf_path, "[general]",
                        "[general]\nskip_vs_projects_upgrade = True", output=client.out)
        client.save(files, clean_first=True)
        client.run("create . Hello/1.2.1@lasote/stable --build")
        self.assertNotIn("devenv", client.out)
        self.assertIn("Skipped sln project upgrade", client.out)

        # Try with x86_64
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86_64")
        self.assertIn("Release|x64", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        # Try with x86
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86")
        self.assertIn("Release|x86", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        # Try with x86 debug
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86 -s build_type=Debug")
        self.assertIn("Debug|x86", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        # Try with a custom property file name
        files[CONANFILE] = conan_build_vs.replace(
                'msbuild.build("MyProject.sln", verbosity="normal")',
                'msbuild.build("MyProject.sln", verbosity="normal", property_file_name="mp.props")')
        client.save(files, clean_first=True)
        client.run("create . Hello/1.2.1@lasote/stable --build -s arch=x86 -s build_type=Debug")
        self.assertIn("Debug|x86", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)
        full_ref = "Hello/1.2.1@lasote/stable:b786e9ece960c3a76378ca4d5b0d0e922f4cedc1"
        pref = PackageReference.loads(full_ref)
        build_folder = client.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.exists(os.path.join(build_folder, "mp.props")))

    @pytest.mark.slow
    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_user_properties_file(self):
        conan_build_vs = textwrap.dedent("""
            from conans import ConanFile, MSBuild

            class HelloConan(ConanFile):
                exports = "*"
                settings = "os", "build_type", "arch", "compiler"

                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln", verbosity="normal",
                                  definitions={"MyCustomDef": "MyCustomValue"},
                                  user_property_file_name="myuser.props")

                def package(self):
                    self.copy(pattern="*.exe")
            """)
        client = TestClient()

        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs
        props = textwrap.dedent("""<?xml version="1.0" encoding="utf-8"?>
            <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ImportGroup Label="PropertySheets" />
              <PropertyGroup Label="UserMacros" />
              <ItemDefinitionGroup>
                <ClCompile>
                  <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
                </ClCompile>
              </ItemDefinitionGroup>
              <ItemGroup />
            </Project>
            """)
        files["myuser.props"] = props

        client.save(files)
        client.run('create . Hello/1.2.1@lasote/stable')
        self.assertNotIn("/EHsc /MD", client.out)
        self.assertIn("/EHsc /MT", client.out)
        self.assertIn("/D MyCustomDef=MyCustomValue", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        full_ref = "Hello/1.2.1@lasote/stable:6cc50b139b9c3d27b3e9042d5f5372d327b3a9f7"
        pref = PackageReference.loads(full_ref)
        build_folder = client.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.exists(os.path.join(build_folder, "myuser.props")))
        conan_props = os.path.join(build_folder, "conan_build.props")
        content = load(conan_props)
        self.assertIn("<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>", content)

    @pytest.mark.slow
    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_user_properties_multifile(self):
        conan_build_vs = textwrap.dedent("""
            from conans import ConanFile, MSBuild

            class HelloConan(ConanFile):
                exports = "*"
                settings = "os", "build_type", "arch", "compiler"

                def build(self):
                    msbuild = MSBuild(self)
                    msbuild.build("MyProject.sln", verbosity="normal",
                                  definitions={"MyCustomDef": "MyCustomValue"},
                                  user_property_file_name=["myuser.props", "myuser2.props"])

                def package(self):
                    self.copy(pattern="*.exe")
            """)
        client = TestClient()

        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs
        props = textwrap.dedent("""<?xml version="1.0" encoding="utf-8"?>
            <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ImportGroup Label="PropertySheets" />
              <PropertyGroup Label="UserMacros" />
              <ItemDefinitionGroup>
                <ClCompile>
                    <PreprocessorDefinitions>MyCustomDef2=MyValue2;%(PreprocessorDefinitions)
                    </PreprocessorDefinitions>
                </ClCompile>
              </ItemDefinitionGroup>
              <ItemGroup />
            </Project>
            """)
        props2 = textwrap.dedent("""<?xml version="1.0" encoding="utf-8"?>
            <Project ToolsVersion="4.0" xmlns="http://schemas.microsoft.com/developer/msbuild/2003">
              <ImportGroup Label="PropertySheets" />
              <PropertyGroup Label="UserMacros" />
              <ItemDefinitionGroup>
                <ClCompile>
                  <RuntimeLibrary>MultiThreaded</RuntimeLibrary>
                </ClCompile>
              </ItemDefinitionGroup>
              <ItemGroup />
            </Project>
            """)
        files["myuser.props"] = props
        files["myuser2.props"] = props2

        client.save(files)
        client.run('create . Hello/1.2.1@lasote/stable')
        self.assertNotIn("/EHsc /MD", client.out)
        self.assertIn("/EHsc /MT", client.out)
        self.assertIn("/D MyCustomDef=MyCustomValue", client.out)
        self.assertIn("/D MyCustomDef2=MyValue2", client.out)
        self.assertIn("Packaged 1 '.exe' file: MyProject.exe", client.out)

        full_ref = "Hello/1.2.1@lasote/stable:6cc50b139b9c3d27b3e9042d5f5372d327b3a9f7"
        pref = PackageReference.loads(full_ref)
        build_folder = client.cache.package_layout(pref.ref).build(pref)
        self.assertTrue(os.path.exists(os.path.join(build_folder, "myuser.props")))
        conan_props = os.path.join(build_folder, "conan_build.props")
        content = load(conan_props)
        self.assertIn("<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>", content)

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_reuse_msbuild_object(self):
        # https://github.com/conan-io/conan/issues/2865
        conan_build_vs = """
from conans import ConanFile, MSBuild

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    exports = "*"
    settings = "os", "build_type", "arch", "compiler", "cppstd"

    def configure(self):
        del self.settings.compiler.runtime
        del self.settings.build_type

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("MyProject.sln", build_type="Release")
        msbuild.build("MyProject.sln", build_type="Debug")
        self.output.info("build() completed")
"""
        client = TestClient()
        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs

        client.save(files)
        client.run("create . danimtb/testing")
        self.assertIn("build() completed", client.out)

    @parameterized.expand([("True",), ("'my_log.binlog'",)])
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    @pytest.mark.tool_visual_studio
    def test_binary_log_build(self, value):
        conan_build_vs = """
from conans import ConanFile, MSBuild

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    exports = "*"
    settings = "os", "build_type", "arch", "compiler"

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("MyProject.sln", output_binary_log=%s)
"""
        client = TestClient()
        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs % value
        client.save(files)
        client.run("install . -s compiler=\"Visual Studio\" -s compiler.version=15")
        client.run("build .")

        if value == "'my_log.binlog'":
            log_name = value[1:1]
            flag = "/bl:%s" % log_name
        else:
            log_name = "msbuild.binlog"
            flag = "/bl"

        self.assertIn(flag, client.out)
        log_path = os.path.join(client.current_folder, log_name)
        self.assertTrue(os.path.exists(log_path))

    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
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
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    @mock.patch("conans.client.build.msbuild.MSBuild.get_version")
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
    def test_get_version(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "compiler.version": "15",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        version = MSBuild.get_version(settings)
        six.assertRegex(self, version, r"(\d+\.){2,3}\d+")
        self.assertGreater(version, "15.1")

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows", reason="Requires MSBuild")
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

    @pytest.mark.tool_visual_studio
    @pytest.mark.skipif(platform.system() != "Windows",
                        reason="Requires Visual Studio installation path")
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
