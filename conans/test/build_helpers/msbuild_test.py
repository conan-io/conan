import platform
import unittest

from nose.plugins.attrib import attr

from conans import tools
from conans.client.build.msbuild import MSBuild
from conans.paths import CONANFILE
from conans.test.utils.conanfile import MockSettings, MockConanfile
from conans.test.utils.tools import TestClient
from conans.test.utils.visual_project_files import get_vs_project_files


class MSBuildTest(unittest.TestCase):

    def dont_mess_with_build_type_test(self):
        settings = MockSettings({"build_type": "Debug",
                                 "compiler": "Visual Studio",
                                 "arch": "x86_64"})
        conanfile = MockConanfile(settings)
        msbuild = MSBuild(conanfile)
        self.assertEquals(msbuild.build_env.flags, ["-Zi", "-Ob0", "-Od"])
        template = msbuild._get_props_file_contents()

        self.assertIn("-Ob0", template)
        self.assertIn("-Od", template)

        msbuild.build_env.flags = ["-Zi"]
        template = msbuild._get_props_file_contents()

        self.assertNotIn("-Ob0", template)
        self.assertNotIn("-Od", template)

    @attr('slow')
    def build_vs_project_test(self):
        if platform.system() != "Windows":
            return
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
