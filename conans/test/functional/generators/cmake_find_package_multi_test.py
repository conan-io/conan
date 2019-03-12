import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr
from parameterized import parameterized

from conans.test.utils.tools import TestClient
from conans.util.files import mkdir


@attr('slow')
class CMakeFindPathMultiGeneratorTest(unittest.TestCase):

    @parameterized.expand([("targets",), ("global",)])
    def test_native_export_multi(self, cmake_mode):
        """
        bye depends on hello. Both use find_package in their CMakeLists.txt
        The consumer depends on bye, using the cmake_find_package_multi generator
        """
        c = TestClient()
        project_folder_name = "project_{}".format(cmake_mode)
        assets_path = os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                   "assets/cmake_find_package_multi")
        c.copy_from_assets(assets_path, ["bye", "hello", project_folder_name])

        # Create packages for hello and bye
        for p in ("hello", "bye"):
            with c.chdir(p):
                for bt in ("Debug", "Release"):
                    c.run("create . user/channel -s build_type={}".format(bt))

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

            mkdir("./build")
            with c.chdir("build"):
                for bt in ("Debug", "Release"):
                    c.run("install .. user/channel -s build_type={}".format(bt))

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
