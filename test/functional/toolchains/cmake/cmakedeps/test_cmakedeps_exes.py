import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_exes():
    conanfile = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class Test(ConanFile):
            name = "mytool"
            version = "0.1"
            package_type = "application"
            settings = "os", "arch", "compiler", "build_type"
            generators = "CMakeToolchain"
            exports_sources = "*"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def layout(self):
                cmake_layout(self)

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                location =  os.path.join(self.package_folder, "bin/mytool.exe").replace("\\", "/")
                self.cpp_info.exes = {"myexe": {"location": location}}
        """)
    main = textwrap.dedent("""
        #include <fstream>

        int main() {
            std::ofstream f("out.c");
        }
        """)
    c = TestClient()
    c.run("new cmake_exe -d name=mytool -d version=0.1")
    c.save({"conanfile.py": conanfile,
            "src/main.cpp": main})
    c.run("create .")

    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeDeps, CMakeToolchain, CMake, cmake_layout
        class Consumer(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            tool_requires = "mytool/0.1"

            def generate(self):
                deps = CMakeDeps(self)
                deps.build_context_activated = ["mytool"]
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

            def layout(self):
                cmake_layout(self)
            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(consumer C)

        find_package(mytool)
        add_custom_command(OUTPUT out.c
                           COMMAND mytool::myexe)
        add_library(myLib out.c)
        """)
    c.save({"conanfile.py": consumer,
            "CMakeLists.txt": cmake}, clean_first=True)
    c.run("build .")
    print(c.out)

