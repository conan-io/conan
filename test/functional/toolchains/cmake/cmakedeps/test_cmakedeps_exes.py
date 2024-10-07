import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_exe():
    conanfile = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake

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

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.exe = "myexe"
                self.cpp_info.location = os.path.join("bin", "mytool")
        """)
    main = textwrap.dedent("""
        #include <iostream>
        #include <fstream>

        int main() {
            std::cout << "Mytool generating out.c!!!!!" << std::endl;
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
        add_custom_command(OUTPUT out.c COMMAND mytool::myexe)
        add_library(myLib out.c)
        """)
    c.save({"conanfile.py": consumer,
            "CMakeLists.txt": cmake}, clean_first=True)
    c.run("build .")
    assert "Conan: Target declared 'mytool::mytool'" in c.out
    assert "Conan: Target declared imported executable 'mytool::myexe'" in c.out
    assert "Mytool generating out.c!!!!!" in c.out


@pytest.mark.tool("cmake")
def test_exe_components():
    conanfile = textwrap.dedent(r"""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake

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

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.components["my1exe"].exe = "mytool1"
                self.cpp_info.components["my1exe"].location = os.path.join("bin", "mytool2")
                self.cpp_info.components["my2exe"].exe = "mytool2"
                self.cpp_info.components["my1exe"].location = os.path.join("bin", "mytool2")
        """)
    main = textwrap.dedent("""
        #include <iostream>
        #include <fstream>

        int main() {{
            std::cout << "Mytool{number} generating out.c!!!!!" << std::endl;
            std::ofstream f("out{number}.c");
        }}
        """)
    cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(proj CXX)

        add_executable(mytool1 src/main1.cpp)
        add_executable(mytool2 src/main2.cpp)

        install(TARGETS mytool1 DESTINATION "." RUNTIME DESTINATION bin)
        install(TARGETS mytool2 DESTINATION "." RUNTIME DESTINATION bin)
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": cmake,
            "src/main1.cpp": main.format(number=1),
            "src/main2.cpp": main.format(number=2)
            })
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
        add_custom_command(OUTPUT out1.c
                           COMMAND mytool::my1exe)
        add_custom_command(OUTPUT out2.c
                           COMMAND mytool::my2exe)
        add_library(myLib out1.c out2.c)
        """)
    c.save({"conanfile.py": consumer,
            "CMakeLists.txt": cmake}, clean_first=True)
    c.run("build .")
    print(c.out)
    assert "Conan: Target declared 'mytool::mytool'" in c.out
    assert "Conan: Target declared imported executable 'mytool::myexe'" in c.out
    assert "Mytool generating out.c!!!!!" in c.out
