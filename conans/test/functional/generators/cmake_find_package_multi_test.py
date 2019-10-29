import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.client.tools import replace_in_file
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

    def cpp_info_name_test(self):
        client = TestClient()
        client.run("new hello/1.0 -s")
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'self.cpp_info.libs = ["hello"]',
                        'self.cpp_info.libs = ["hello"]\n        self.cpp_info.name = "MYHELLO"',
                        output=client.out)
        client.run("create .")
        client.run("new hello2/1.0 -s")
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'self.cpp_info.libs = ["hello"]',
                        'self.cpp_info.libs = ["hello"]\n        self.cpp_info.name = "MYHELLO2"',
                        output=client.out)
        replace_in_file(os.path.join(client.current_folder, "conanfile.py"),
                        'exports_sources = "src/*"',
                        'exports_sources = "src/*"\n    requires = "hello/1.0"',
                        output=client.out)
        client.run("create .")
        cmakelists = """
project(consumer)
cmake_minimum_required(VERSION 3.1)
find_package(MYHELLO2)

get_target_property(tmp MYHELLO2::MYHELLO2 INTERFACE_LINK_LIBRARIES)
message("Target libs: ${tmp}")
"""
        conanfile = """
from conans import ConanFile, CMake


class Conan(ConanFile):
    settings = "build_type"
    requires = "hello2/1.0"
    generators = "cmake_find_package_multi"

    def build(self):
        cmake = CMake(self)
        cmake.configure()
        """
        client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists})
        client.run("install .")
        client.run("build .")
        self.assertIn("Target libs: $<$<CONFIG:Release>:CONAN_LIB::MYHELLO2_hello_RELEASE;>;"
                      "$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;"
                      "$<$<CONFIG:Debug>:;>;$"
                      "<$<CONFIG:Release>:CONAN_LIB::MYHELLO_hello_RELEASE;>;"
                      "$<$<CONFIG:RelWithDebInfo>:;>;"
                      "$<$<CONFIG:MinSizeRel>:;>;"
                      "$<$<CONFIG:Debug>:;>",
                      client.out)
