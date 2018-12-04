import os
import platform
import unittest

import mock
from nose.plugins.attrib import attr
from parameterized import parameterized

from conans.client.build.msbuild import MSBuild
from conans.errors import ConanException
from conans.model.version import Version
from conans.paths import CONANFILE
from conans.test.utils.conanfile import MockSettings, MockConanfile
from conans.test.utils.tools import TestClient
from conans.test.utils.visual_project_files import get_vs_project_files
from conans.client import tools


class MSBuildTest(unittest.TestCase):

    def dont_mess_with_build_type_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64",
                                 "compiler.runtime": "MDd"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        self.assertEquals(msbuild.build_env.flags, [])
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

    @attr('slow')
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def build_vs_project_test(self):
        conan_build_vs = """
from conans import ConanFile, MSBuild

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2.1"
    exports = "*"
    settings = "os", "build_type", "arch", "compiler", "cppstd"

    def build(self):
        msbuild = MSBuild(self)
        msbuild.build("MyProject.sln")

    def package(self):
        self.copy(pattern="*.exe")

"""
        client = TestClient()

        # Test cpp standard stuff

        files = get_vs_project_files(std="cpp17_2015")
        files[CONANFILE] = conan_build_vs

        client.save(files)
        error = client.run('create . Hello/1.2.1@lasote/stable -s cppstd=11 -s '
                           'compiler="Visual Studio" -s compiler.version=14', ignore_error=True)
        self.assertTrue(error)
        client.run('create . Hello/1.2.1@lasote/stable -s cppstd=17 '
                   '-s compiler="Visual Studio" -s compiler.version=14')
        self.assertIn("Copied 1 '.exe' file: MyProject.exe", client.user_io.out)

        files = get_vs_project_files()
        files[CONANFILE] = conan_build_vs

        # Try to not update the project
        client.client_cache._conan_config = None  # Invalidate cached config
        tools.replace_in_file(client.client_cache.conan_conf_path, "[general]",
                              "[general]\nskip_vs_projects_upgrade = True")
        client.save(files, clean_first=True)
        client.run("create . Hello/1.2.1@lasote/stable --build")
        self.assertNotIn("devenv", client.user_io.out)
        self.assertIn("Skipped sln project upgrade", client.user_io.out)

        # Try with x86_64
        client.save(files)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86_64")
        self.assertIn("Release|x64", client.user_io.out)
        self.assertIn("Copied 1 '.exe' file: MyProject.exe", client.user_io.out)

        # Try with x86
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86")
        self.assertIn("Release|x86", client.user_io.out)
        self.assertIn("Copied 1 '.exe' file: MyProject.exe", client.user_io.out)

        # Try with x86 debug
        client.save(files, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Hello/1.2.1@lasote/stable --build -s arch=x86 -s build_type=Debug")
        self.assertIn("Debug|x86", client.user_io.out)
        self.assertIn("Copied 1 '.exe' file: MyProject.exe", client.user_io.out)

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
    def reuse_msbuild_object_test(self):
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
        self.assertRegexpMatches(version, "(\d+\.){2,3}\d+")
        self.assertGreater(version, "15.1")

    @parameterized.expand([("True",), ("'my_log.binlog'",)])
    @unittest.skipUnless(platform.system() == "Windows", "Requires MSBuild")
    def binary_log_build_test(self, value):
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
