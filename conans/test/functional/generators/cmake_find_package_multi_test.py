import os
import platform
import textwrap
import unittest

from nose.plugins.attrib import attr

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID, replace_in_file
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
        self.assertEqual(set(os.listdir(modules_path)),
                         {"FindFindModule.cmake", "my-module.cmake"})
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
        self.assertIn("Printing using a external module!", client.out)

    def cmake_find_package_system_libs_test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, tools

            class Test(ConanFile):
                name = "Test"
                version = "0.1"
                settings = "build_type"
                def package_info(self):
                    self.cpp_info.libs = ["lib1"]
                    if self.settings.build_type == "Debug":
                        self.cpp_info.system_libs.append("sys1d")
                    else:
                        self.cpp_info.system_libs.append("sys1")
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
        cmakelists_release = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
            find_package(Test)
            message("System libs: ${Test_SYSTEM_LIBS_RELEASE}")
            message("Libraries to Link: ${Test_LIBS_RELEASE}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            """)
        cmakelists_debug = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.1)
            project(consumer CXX)
            set(CMAKE_PREFIX_PATH ${CMAKE_BINARY_DIR})
            set(CMAKE_MODULE_PATH ${CMAKE_BINARY_DIR})
            find_package(Test)
            message("System libs: ${Test_SYSTEM_LIBS_DEBUG}")
            message("Libraries to Link: ${Test_LIBS_DEBUG}")
            get_target_property(tmp Test::Test INTERFACE_LINK_LIBRARIES)
            message("Target libs: ${tmp}")
            """)
        for build_type in ["Release", "Debug"]:
            cmakelists = cmakelists_release if build_type == "Release" else cmakelists_debug
            client.save({"conanfile.txt": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
            client.run("install conanfile.txt --build missing -s build_type=%s" % build_type)
            client.run_command('cmake . -DCMAKE_BUILD_TYPE={0}'.format(build_type))

            library_name = "sys1d" if build_type == "Debug" else "sys1"
            self.assertIn("System libs: %s" % library_name, client.out)
            self.assertIn("Libraries to Link: lib1", client.out)
            self.assertNotIn("-- Library %s not found in package, might be system one" %
                             library_name, client.out)
            if build_type == "Release":
                target_libs = "$<$<CONFIG:Release>:lib1;sys1;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:;>"
            else:
                target_libs = "$<$<CONFIG:Release>:;>;$<$<CONFIG:RelWithDebInfo>:;>;$<$<CONFIG:MinSizeRel>:;>;$<$<CONFIG:Debug>:lib1;sys1d;>"
            self.assertIn("Target libs: %s" % target_libs, client.out)

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
