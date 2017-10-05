from conans.test.utils.tools import TestClient
import unittest
from conans.paths import CONANFILE
from conans.model.ref import PackageReference
import os
from conans.util.files import load, mkdir

conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    generators = "cmake"

    def build(self):
        self.output.info("INCLUDE PATH: %s" % self.deps_cpp_info.include_paths[0])
        self.output.info("HELLO ROOT PATH: %s" % self.deps_cpp_info["Hello"].rootpath)
        self.output.info("HELLO INCLUDE PATHS: %s" % self.deps_cpp_info["Hello"].include_paths[0])
"""

conanfile_dep = """
from conans import ConanFile
from conans.tools import mkdir
import os

class AConan(ConanFile):
    name = "Hello"
    version = "0.1"

    def package(self):
        mkdir(os.path.join(self.package_folder, "include"))
"""


class ConanBuildTest(unittest.TestCase):

    def build_error_test(self):
        """ If not using -g txt generator, and build() requires self.deps_cpp_info,
        or self.deps_user_info it will fail
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export lasote/testing")
        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing")
        error = client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: PROJECT: Error in build() method, line 9", client.user_io.out)
        self.assertIn("self.deps_cpp_info not defined", client.user_io.out)

        conanfile_user_info = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello/0.1@lasote/testing"
    generators = "cmake"

    def build(self):
        self.deps_user_info.VAR
"""
        client.save({CONANFILE: conanfile_user_info}, clean_first=True)
        client.run("install --build=missing")
        error = client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: PROJECT: Error in build() method, line 9", client.user_io.out)
        self.assertIn("self.deps_user_info not defined", client.user_io.out)

    def build_test(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        client.save({CONANFILE: conanfile_dep})
        client.run("export lasote/testing")

        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing -g txt")

        client.run("build .")
        ref = PackageReference.loads("Hello/0.1@lasote/testing:"
                                     "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        package_folder = client.paths.package(ref).replace("\\", "/")
        self.assertIn("Project: INCLUDE PATH: %s/include" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO ROOT PATH: %s" % package_folder, client.user_io.out)
        self.assertIn("Project: HELLO INCLUDE PATHS: %s/include"
                      % package_folder, client.user_io.out)

    def build_different_folders_test(self):
        conanfile = """
import os
from conans import ConanFile

class AConan(ConanFile):
    generators = "cmake"

    def build(self):
        self.output.warn("Build folder=>%s" % self.build_folder)
        self.output.warn("Src folder=>%s" % self.source_folder)
        self.output.warn("Package folder=>%s" % self.package_folder)
        assert(os.path.exists(self.build_folder))
        assert(os.path.exists(self.source_folder))
        # package_folder will be created manually or by the CMake helper when local invocation
        assert(not os.path.exists(self.package_folder))
"""

        client = TestClient()
        client.save({CONANFILE: conanfile})
        # Try relative to cwd
        client.run("build . --build_folder build1 --package_folder pkg")
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build1"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "build1", "pkg"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try default package folder
        client.run("build . --build_folder build1 --package_folder package1")
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build1"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "build1",
                                                          "package"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try absolute package folder
        client.run("build . --build_folder build1 --package_folder '%s'" %
                   os.path.join(client.current_folder, "mypackage"))
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "build1"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "mypackage"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try absolute build and relative package
        client.run("build . --build_folder '%s' --package_folder relpackage" %
                   os.path.join(client.current_folder, "other/mybuild"))
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "other/mybuild"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "other", "mybuild",
                                                          "relpackage"),
                      client.out)
        self.assertIn("Src folder=>%s" % client.current_folder, client.out)

        # Try different source
        error = client.run("build . --source_folder '%s' --build_folder other/build" %
                           os.path.join(client.current_folder, "mysrc"), ignore_error=True)
        self.assertTrue(error)  # src is not created automatically, it makes no sense
        mkdir(os.path.join(client.current_folder, "mysrc"))

        client.run("build . --source_folder '%s' --build_folder other/build" %
                           os.path.join(client.current_folder, "mysrc"))
        self.assertIn("Build folder=>%s" % os.path.join(client.current_folder, "other", "build"),
                      client.out)
        self.assertIn("Package folder=>%s" % os.path.join(client.current_folder, "other", "build"),
                      client.out)
        self.assertIn("Src folder=>%s" % os.path.join(client.current_folder, "mysrc"), client.out)

    def build_dots_names_test(self):
        """ Try to reuse variables loaded from txt generator => deps_cpp_info
        """
        client = TestClient()
        conanfile_dep = """
from conans import ConanFile

class AConan(ConanFile):
    pass
"""
        client.save({CONANFILE: conanfile_dep})
        client.run("create Hello.Pkg/0.1@lasote/testing")
        client.run("create Hello-Tools/0.1@lasote/testing")
        conanfile_scope_env = """
from conans import ConanFile

class AConan(ConanFile):
    requires = "Hello.Pkg/0.1@lasote/testing", "Hello-Tools/0.1@lasote/testing"

    def build(self):
        self.output.info("HELLO ROOT PATH: %s" % self.deps_cpp_info["Hello.Pkg"].rootpath)
        self.output.info("HELLO ROOT PATH: %s" % self.deps_cpp_info["Hello-Tools"].rootpath)
"""
        client.save({CONANFILE: conanfile_scope_env}, clean_first=True)
        client.run("install --build=missing -g txt")
        client.run("build .")
        self.assertIn("Hello.Pkg/0.1/lasote/testing", client.out)
        self.assertIn("Hello-Tools/0.1/lasote/testing", client.out)

    def build_cmake_install_test(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile, CMake

class AConan(ConanFile):
    settings = "os", "compiler", "build_type", "arch"
    def build(self):
        cmake = CMake(self)
        cmake.configure()
        cmake.install()
"""
        cmake = """set(CMAKE_CXX_COMPILER_WORKS 1)
project(Chat NONE)
cmake_minimum_required(VERSION 2.8.12)

        install(FILES header.h DESTINATION include)
"""
        client.save({CONANFILE: conanfile,
                     "CMakeLists.txt": cmake,
                     "header.h": "my header h!!"})
        client.run("install")
        client.run("build .")  # Won't fail, by default the package_folder is build_folder/package
        header = load(os.path.join(client.current_folder, "package/include/header.h"))
        self.assertEqual(header, "my header h!!")

        client.save({CONANFILE: conanfile,
                     "CMakeLists.txt": cmake,
                     "header.h": "my header3 h!!"}, clean_first=True)
        client.run("build -pf=mypkg .")
        header = load(os.path.join(client.current_folder, "mypkg/include/header.h"))
        self.assertEqual(header, "my header3 h!!")

        client.save({CONANFILE: conanfile,
                     "CMakeLists.txt": cmake,
                     "header.h": "my header2 h!!"}, clean_first=True)
        client.run("build . -pf=mypkg -bf=build")
        header = load(os.path.join(client.current_folder, "build/mypkg/include/header.h"))
        self.assertEqual(header, "my header2 h!!")
