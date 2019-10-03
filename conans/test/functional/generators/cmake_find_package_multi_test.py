import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.test.utils.tools import TestClient
from conans.util.files import load


@attr('slow')
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    def test_native_export_multi(self):
        """
        bye depends on hello. Both use find_package in their CMakeLists.txt
        The consumer depends on bye, using the cmake_find_package_multi generator
        """
        c = TestClient()
        project_folder_name = "project_targets"
        assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "assets/cmake_find_package_multi")
        c.copy_from_assets(assets_path, ["bye", "hello", project_folder_name])

        # Create packages for hello and bye
        for p in ("hello", "bye"):
            for bt in ("Debug", "Release"):
                c.run("create {} user/channel -s build_type={}".format(p, bt))

        with c.chdir(project_folder_name):
            # Save conanfile and example
            conanfile = textwrap.dedent("""
                [requires]
                bye/1.0@user/channel

                [generators]
                cmake_find_package_multi
                """)
            example_cpp = textwrap.dedent("""
                #include <iostream>
                #include "bye.h"

                int main() {
                    bye();
                }
                """)
            c.save({"conanfile.txt": conanfile, "example.cpp": example_cpp})

            with c.chdir("build"):
                for bt in ("Debug", "Release"):
                    c.run("install .. user/channel -s build_type={}".format(bt))

                # Test that we are using find_dependency with the NO_MODULE option
                # to skip finding first possible FindBye somewhere
                self.assertIn("find_dependency(hello REQUIRED NO_MODULE)",
                              load(os.path.join(c.current_folder, "byeConfig.cmake")))

                if platform.system() == "Windows":
                    c.run_command('cmake .. -G "Visual Studio 15 Win64"')
                    c.run_command('cmake --build . --config Debug')
                    c.run_command('cmake --build . --config Release')

                    c.run_command('Debug\\example.exe')
                    self.assertIn("Hello World Debug!", c.out)
                    self.assertIn("bye World Debug!", c.out)

                    c.run_command('Release\\example.exe')
                    self.assertIn("Hello World Release!", c.out)
                    self.assertIn("bye World Release!", c.out)
                else:
                    for bt in ("Debug", "Release"):
                        c.run_command('cmake .. -DCMAKE_BUILD_TYPE={}'.format(bt))
                        c.run_command('cmake --build .')
                        c.run_command('./example')
                        self.assertIn("Hello World {}!".format(bt), c.out)
                        self.assertIn("bye World {}!".format(bt), c.out)
                        os.remove(os.path.join(c.current_folder, "example"))

    @unittest.skipUnless(platform.system() != "Windows", "Skip Visual Studio config for build type")
    def cmake_find_package_system_deps_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Test(ConanFile):
                name = "Test"
                version = "0.1"
                settings = "build_type"
                def package_info(self):
                    if self.settings.build_type == "Debug":
                        self.cpp_info.system_deps.append("sys1d")
                    else:
                        self.cpp_info.system_deps.append("sys1")
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("export .")

        conanfile = textwrap.dedent("""
            [requires]
            Test/0.1

            [generators]
            cmake_find_package_multi
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
            find_package(Test)
            message("System deps: ${Test_SYSTEM_DEPS}")
            message("Libraries to Link: ${Test_LIBS}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            """)
        client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists})
        for build_type in ["Release", "Debug"]:
            client.run("install conanfile.txt --build missing -s build_type=%s" % build_type)
            client.run_command('cmake .. -DCMAKE_BUILD_TYPE={}'.format(build_type))
            client.run_command('cmake --build .')

            library_name = "sys1d" if build_type == "Debug" else "sys1"
            self.assertIn("System deps: %s" % library_name, client.out)
            self.assertIn("Libraries to Link: %s" % library_name, client.out)
            self.assertIn("-- Library %s not found in package, might be system one" % library_name,
                          client.out)
            self.assertIn("Target libs: %s" % library_name, client.out)
