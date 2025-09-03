import os
import textwrap
import unittest

from conan.test.utils.tools import TestClient


class MultiCMakeTest(unittest.TestCase):

    def test_create(self):
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps


            class multiRecipe(ConanFile):
                settings = "os", "compiler", "build_type", "arch"

                exports_sources = "cmake_one/CMakeLists.txt", "cmake_two/CMakeLists.txt", "src_one/*", "src_two/*"

                def layout(self):
                    cmake_layout(self)

                def generate(self):
                    deps = CMakeDeps(self)
                    deps.generate()
                    tc = CMakeToolchain(self)
                    tc.generate()

                def build(self):
                    cmake = CMake(self)
                    cmake.configure(build_script_folder="cmake_one", build_subfolder="one", source_subfolder="src_one")
                    cmake.build(build_subfolder="one")
                    cmake.configure(build_script_folder="cmake_two", build_subfolder="two", source_subfolder="src_two")
                    cmake.build(build_subfolder="two")

                def package(self):
                    cmake = CMake(self)
                    cmake.install(build_subfolder="one")
                    cmake.install(build_subfolder="two")

                def package_info(self):
                    self.cpp_info.libs = ["hello_two"]
            """)

        hello_cpp = textwrap.dedent("""
            #include <iostream>
            #include "hello_{name}.h"

            void hello_{name}() {{
                std::cout << "Hello, World {name}!" << std::endl;
            }}
            """)

        hello_h = textwrap.dedent("""
            #ifndef HELLO_{name}_H
            #define HELLO_{name}_H

            void hello_{name}();

            #endif
            """)

        cmakelist = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(hello_{name} CXX)

            add_library(hello_{name} ${{CONAN_SOURCE_DIR}}/hello_{name}.cpp)
            target_include_directories(hello_{name} PUBLIC ${{CONAN_SOURCE_DIR}})

            set_target_properties(hello_{name} PROPERTIES PUBLIC_HEADER "${{CONAN_SOURCE_DIR}}/hello_{name}.h")
            install(TARGETS hello_{name})
            """)

        test_cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(test_package LANGUAGES C)

            find_package(multi REQUIRED CONFIG)

            add_executable(${PROJECT_NAME} test_package.c)
            target_link_libraries(${PROJECT_NAME} PRIVATE multi::multi)
            """)

        test_conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.build import can_run
        from conan.tools.cmake import cmake_layout, CMake
        import os


        class TestPackageConan(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeDeps", "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                if can_run(self):
                    bin_path = os.path.join(self.cpp.build.bindir, "test_package")
                    self.run(bin_path, env="conanrun")
            """)

        test_package_c = textwrap.dedent("""
            #include "hello_two.h"

            int main(void) {
                hello_two();
                return EXIT_SUCCESS;
            }
            """)

        client = TestClient(path_with_spaces=False)
        client.save({"conanfile.py": conanfile,
                     "cmake_one/CMakeLists.txt": cmakelist.format(name="one"),
                     "cmake_two/CMakeLists.txt": cmakelist.format(name="two"),
                     "src_one/hello_one.h": hello_h.format(name="one"),
                     "src_one/hello_one.cpp": hello_cpp.format(name="one"),
                     "src_two/hello_two.h": hello_h.format(name="two"),
                     "src_two/hello_two.cpp": hello_cpp.format(name="two"),})
                    #  "test_package/CMakeLists.txt": test_cmake,
                    #  "test_package/conanfile.py": test_conanfile,
                    #  "test_package/test_package.c": test_package_c})

        client.run("create . --name=multi --version=0.1")
        self.assertIn("[100%] Built target hello_one", client.out)
        self.assertIn("[100%] Built target hello_two", client.out)
        self.assertIn("multi/0.1: package(): Packaged 2 '.h' files: hello_one.h, hello_two.h", client.out)
        self.assertIn("multi/0.1: package(): Packaged 2 '.a' files: libhello_one.a, libhello_two.a", client.out)
        package_folder = client.created_layout().package()

        self.assertTrue(os.path.exists(os.path.join(package_folder, "one", "include", "hello_one.h")))
        self.assertTrue(os.path.exists(os.path.join(package_folder, "one", "lib", "libhello_one.a")))

        self.assertTrue(os.path.exists(os.path.join(package_folder, "two", "include", "hello_two.h")))
        self.assertTrue(os.path.exists(os.path.join(package_folder, "two", "lib", "libhello_two.a")))
