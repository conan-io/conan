import os
import platform
import unittest

from nose.plugins.attrib import attr
from parameterized import parameterized

from conans.client import tools
from conans.model.ref import PackageReference
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
from conans.test.utils.visual_project_files import get_vs_project_files


class MSBuildTest(unittest.TestCase):

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
        client.run('create . Hello/1.2.1@lasote/stable -s cppstd=11 -s '
                   'compiler="Visual Studio" -s compiler.version=14', assert_error=True)
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

        # Try with a custom property file name
        files[CONANFILE] = conan_build_vs.replace('msbuild.build("MyProject.sln")',
                                                  'msbuild.build("MyProject.sln", '
                                                  'property_file_name="myprops.props")')
        client.save(files, clean_first=True)
        client.run("create . Hello/1.2.1@lasote/stable --build -s arch=x86 -s build_type=Debug")
        self.assertIn("Debug|x86", client.user_io.out)
        self.assertIn("Copied 1 '.exe' file: MyProject.exe", client.user_io.out)
        full_ref = "Hello/1.2.1@lasote/stable:b786e9ece960c3a76378ca4d5b0d0e922f4cedc1"
        pref = PackageReference.loads(full_ref)
        build_folder = client.client_cache.build(pref)
        self.assertTrue(os.path.exists(os.path.join(build_folder, "myprops.props")))

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
