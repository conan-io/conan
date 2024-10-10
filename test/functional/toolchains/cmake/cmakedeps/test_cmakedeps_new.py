import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
class TestExes:
    def test_exe(self):
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
                    self.cpp_info.exe = "mytool"
                    self.cpp_info.set_property("cmake_target_name", "MyTool::myexe")
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
            add_custom_command(OUTPUT out.c COMMAND MyTool::myexe)
            add_library(myLib out.c)
            """)
        c.save({"conanfile.py": consumer,
                "CMakeLists.txt": cmake}, clean_first=True)
        c.run("build . -c tools.cmake.cmakedeps:new=True")
        assert "Conan: Target declared imported executable 'MyTool::myexe'" in c.out
        assert "Mytool generating out.c!!!!!" in c.out

    def test_exe_components(self):
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
                    self.cpp_info.components["my1exe"].set_property("cmake_target_name", "MyTool::my1exe")
                    self.cpp_info.components["my1exe"].location = os.path.join("bin", "mytool1")
                    self.cpp_info.components["my2exe"].exe = "mytool2"
                    self.cpp_info.components["my2exe"].set_property("cmake_target_name", "MyTool::my2exe")
                    self.cpp_info.components["my2exe"].location = os.path.join("bin", "mytool2")
            """)
        main = textwrap.dedent("""
            #include <iostream>
            #include <fstream>

            int main() {{
                std::cout << "Mytool{number} generating out{number}.c!!!!!" << std::endl;
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
            add_custom_command(OUTPUT out1.c COMMAND MyTool::my1exe)
            add_custom_command(OUTPUT out2.c COMMAND MyTool::my2exe)
            add_library(myLib out1.c out2.c)
            """)
        c.save({"conanfile.py": consumer,
                "CMakeLists.txt": cmake}, clean_first=True)
        c.run("build . -c tools.cmake.cmakedeps:new=True")
        assert "Conan: Target declared imported executable 'MyTool::my1exe'" in c.out
        assert "Mytool1 generating out1.c!!!!!" in c.out
        assert "Conan: Target declared imported executable 'MyTool::my2exe'" in c.out
        assert "Mytool2 generating out2.c!!!!!" in c.out


@pytest.mark.tool("cmake")
class TestLibs:
    def test_libs(self, matrix_client):
        c = matrix_client
        c.run("new cmake_lib -d name=app -d version=0.1 -d requires=matrix/1.0")
        c.run("build . -c tools.cmake.cmakedeps:new=True")
        assert "Conan: Target declared imported STATIC library 'matrix::matrix'" in c.out

    def test_libs_components(self, matrix_client_components):
        """
        explicit usage of components
        """
        c = matrix_client_components

        # TODO: Check that find_package(.. COMPONENTS nonexisting) fails
        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE matrix::module)
            """)
        app_cpp = textwrap.dedent("""
            #include "module.h"
            int main() { module();}
            """)
        c.save({"CMakelists.txt": cmake,
                "src/app.cpp": app_cpp})
        c.run("build . -c tools.cmake.cmakedeps:new=True")
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out

    def test_libs_components_default(self, matrix_client_components):
        """
        Test that the default components are used when no component is specified
        """
        c = matrix_client_components

        c.run("new cmake_exe -d name=app -d version=0.1 -d requires=matrix/1.0")

        app_cpp = textwrap.dedent("""
            #include "module.h"
            int main() { module();}
            """)
        cmake = textwrap.dedent("""
            cmake_minimum_required(VERSION 3.15)
            project(app CXX)

            find_package(matrix CONFIG REQUIRED)
            add_executable(app src/app.cpp)
            target_link_libraries(app PRIVATE matrix::matrix)
            """)
        c.save({"src/app.cpp": app_cpp,
                "CMakeLists.txt": cmake})
        c.run("build . -c tools.cmake.cmakedeps:new=True")
        assert "Conan: Target declared imported STATIC library 'matrix::vector'" in c.out
        assert "Conan: Target declared imported STATIC library 'matrix::module'" in c.out
