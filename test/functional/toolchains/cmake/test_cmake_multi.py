import os
import platform
import textwrap

from conan.test.utils.tools import TestClient


def test_multi_cMake():
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps
        import os


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

            def build_one(self):
                cmake = CMake(self)
                cmake.configure(build_script_folder="cmake_one", build_subfolder="one")
                cmake.build(build_subfolder="one")
                # cmake.install(build_subfolder="one")

            def build_two(self):
                cmake = CMake(self)
                # CMAKE_PREFIX_PATH
                cmake.configure(build_script_folder="cmake_two", build_subfolder="two")
                cmake.build(build_subfolder="two")

            def build(self):
                self.build_one()
                self.build_two()

            def package(self):
                cmake = CMake(self)
                cmake.install(build_subfolder="two")

            def package_info(self):
                self.cpp_info.libs = ["hello_two"]
                self.cpp_info.includedirs = ['two/include']
                self.cpp_info.libdirs = ['two/lib']
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
        project(hello_{name} LANGUAGES CXX)

        add_library(hello_{name} ../src_{name}/hello_{name}.cpp)
        target_include_directories(hello_{name} PUBLIC ../src_{name})

        set_target_properties(hello_{name} PROPERTIES PUBLIC_HEADER "../src_{name}/hello_{name}.h")
        install(TARGETS hello_{name})
        """)

    client = TestClient()
    client.save({"conanfile.py": conanfile,
                    "cmake_one/CMakeLists.txt": cmakelist.format(name="one"),
                    "cmake_two/CMakeLists.txt": cmakelist.format(name="two"),
                    "src_one/hello_one.h": hello_h.format(name="one"),
                    "src_one/hello_one.cpp": hello_cpp.format(name="one"),
                    "src_two/hello_two.h": hello_h.format(name="two"),
                    "src_two/hello_two.cpp": hello_cpp.format(name="two")})

    client.run("create . --name=multi --version=0.1")

    if platform.system() != "Windows":
        "[100%] Built target hello_one" in client.out
        "[100%] Built target hello_two" in client.out
        "multi/0.1: package(): Packaged 1 '.h' file: hello_two.h" in client.out
        "multi/0.1: package(): Packaged 1 '.a' file: libhello_two.a" in client.out
        package_folder = client.created_layout().package()

        assert not os.path.exists(os.path.join(package_folder, "one", "include", "hello_one.h"))
        assert not os.path.exists(os.path.join(package_folder, "one", "lib", "libhello_one.a"))

        assert os.path.exists(os.path.join(package_folder, "two", "include", "hello_two.h"))
        assert os.path.exists(os.path.join(package_folder, "two", "lib", "libhello_two.a"))
    else:
        "multi/0.1: package(): Packaged 1 '.h' file: hello_two.h" in client.out
        "multi/0.1: package(): Packaged 1 '.lib' file: hello_two.lib" in client.out
        package_folder = client.created_layout().package()

        assert not os.path.exists(os.path.join(package_folder, "one", "include", "hello_one.h"))
        assert not os.path.exists(os.path.join(package_folder, "one", "lib", "hello_one.lib"))

        assert os.path.exists(os.path.join(package_folder, "two", "include", "hello_two.h"))
        assert os.path.exists(os.path.join(package_folder, "two", "lib", "hello_two.lib"))
