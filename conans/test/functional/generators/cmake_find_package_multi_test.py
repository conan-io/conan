import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
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

    def build_modules_test(self):
        conanfile = textwrap.dedent("""
            import os
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "test"
                version = "1.0"
                exports_sources = ["my-module.cmake", "FindFindModule.cmake"]

                def package(self):
                    self.copy("*.cmake", dst="share/cmake")

                def package_info(self):
                    # Only first module is defined
                    # (the other one should be found by CMAKE_MODULE_PATH in builddirs)
                    builddir = os.path.join("share", "cmake")
                    module = os.path.join(builddir, "my-module.cmake")
                    self.cpp_info.build_modules.append(module)
                    self.cpp_info.builddirs = [builddir]
        """)
        # This is a module that has other find_package() calls
        my_module = textwrap.dedent("""
            find_package(FindModule REQUIRED)
            """)
        # This is a module that defines some functionality
        find_module = textwrap.dedent("""
            function(conan_message MESSAGE_OUTPUT)
                message(${ARGV${0}})
            endfunction()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile, "my-module.cmake": my_module,
                     "FindFindModule.cmake": find_module})
        client.run("create .")
        ref = ConanFileReference("test", "1.0", None, None)
        pref = PackageReference(ref, NO_SETTINGS_PACKAGE_ID, None)
        package_path = client.cache.package_layout(ref).package(pref)
        modules_path = os.path.join(package_path, "share", "cmake")
        self.assertListEqual(os.listdir(modules_path), ["FindFindModule.cmake", "my-module.cmake"])
        consumer = textwrap.dedent("""
            from conans import ConanFile, CMake

            class Conan(ConanFile):
                name = "consumer"
                version = "1.0"
                settings = "os", "compiler", "build_type", "arch"
                exports_sources = ["CMakeLists.txt"]
                generators = "cmake_find_package_multi"
                requires = "test/1.0"

                def build(self):
                    cmake = CMake(self)
                    cmake.configure()
                    cmake.build()
            """)
        cmakelists = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.0)
            project(test)
            find_package(test)
            conan_message("Printing using a external module!")
            """)
        client.save({"conanfile.py": consumer, "CMakeLists.txt": cmakelists})
        client.run("create .")
        print(client.out)
        self.assertIn("Printing using a external module!", client.out)
