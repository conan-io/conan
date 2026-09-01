import os
import platform
import textwrap

import pytest

from conan.tools.files import replace_in_file
from conan.test.utils.mocks import ConanFileMock

from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.mark.skipif(platform.system() != "Linux", reason="No OS specific test")
@pytest.mark.tool("cmake")
def test_cpp_info_sources():
    c = TestClient()
    c.run("new cmake_lib -d name=hello -d version=1.0")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy

        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"
            exports_sources = "src/*", "include/*"
            package_type = "header-library"

            def package(self):
                copy(self, "*.h", self.source_folder, self.package_folder)
                copy(self, "*.cpp", self.source_folder, self.package_folder)

            def package_info(self):
                self.cpp_info.sources = ["src/hello.cpp"]
    """)
    c.save({"conanfile.py": conanfile})
    # Check that the hello library builds in test_package
    c.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")
    # Check content of the generated files
    c.run(f"install --requires=hello/1.0 -g=CMakeConfigDeps")
    cmake = c.load("hello-Targets-release.cmake")
    assert "add_library(hello::hello INTERFACE IMPORTED)" in cmake
    assert "set_property(TARGET hello::hello APPEND PROPERTY INTERFACE_SOURCES\n"\
           "             $<$<CONFIG:RELEASE>:${hello_PACKAGE_FOLDER_RELEASE}/src/hello.cpp>)" in cmake


@pytest.mark.skipif(platform.system() != "Linux", reason="No OS specific test")
@pytest.mark.tool("cmake")
def test_cpp_info_component_sources():
    c = TestClient()
    c.run("new cmake_lib -d name=hello -d version=1.0")
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy

        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"
            exports_sources = "src/*", "include/*"
            package_type = "header-library"

            def package(self):
                copy(self, "*.h", self.source_folder, self.package_folder)
                copy(self, "*.cpp", self.source_folder, self.package_folder)

            def package_info(self):
                self.cpp_info.components["my_comp"].sources = ["src/hello.cpp", "src/other.cpp"]
    """)
    c.save({
        "conanfile.py": conanfile,
        "src/other.cpp": "",
    })

    # Make test_package link with component's target
    test_package_cmakelists_path = os.path.join(c.current_folder, "test_package", "CMakeLists.txt")
    replace_in_file(ConanFileMock(), test_package_cmakelists_path, "hello::hello", "hello::my_comp")
    test_package_cmakelists_content = c.load(test_package_cmakelists_path)
    assert "target_link_libraries(example hello::my_comp)" in test_package_cmakelists_content
    # Check that the hello library builds in test_package
    c.run(f"create . -c tools.cmake.cmakedeps:new={new_value}")
    # Check the content of the generated files
    c.run(f"install --requires=hello/1.0 -g=CMakeConfigDeps")
    cmake = c.load("hello-Targets-release.cmake")
    assert "add_library(hello::hello INTERFACE IMPORTED)" in cmake
    assert "add_library(hello::my_comp INTERFACE IMPORTED)" in cmake
    assert "set_property(TARGET hello::my_comp APPEND PROPERTY INTERFACE_SOURCES\n"\
           "             $<$<CONFIG:RELEASE>:${hello_PACKAGE_FOLDER_RELEASE}/src/hello.cpp"\
           " ${hello_PACKAGE_FOLDER_RELEASE}/src/other.cpp>)" in cmake


#@pytest.mark.skipif(platform.system() != "Linux", reason="No OS specific test")
@pytest.mark.tool("cmake")
def test_cpp_info_sources():
    c = TestClient()
    c.save({"src/hello.cpp": '#include <iostream>\nvoid hello() {std::cout << "Hello, world!";}',})
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import copy

        class HelloConan(ConanFile):
            name = "hello"
            version = "1.0"
            exports_sources = "src/*", "include/*"
            package_type = "header-library"

            def package(self):
                copy(self, "*.cpp", self.source_folder, self.package_folder)

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.sources = ["src/hello.cpp"]
    """)

    c.save({"conanfile.py": conanfile})
    c.run("create")

    cml = textwrap.dedent("""
    set(CMAKE_CXX_COMPILER_WORKS 1)
    set(CMAKE_CXX_ABI_COMPILED 1)
    cmake_minimum_required(VERSION 3.15)
    project(example CXX)
    add_executable(example main.cpp main.h)

    find_package(hello REQUIRED CONFIG)
    target_link_libraries(example hello::hello)
    """)
    consumer = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain, CMakeConfigDeps, cmake_layout
    class Consumer(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "CMakeConfigDeps", "CMakeToolchain"
        requires = "hello/1.0"

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            self.run(os.path.join(self.cpp.build.bindir, "example"), env="conanrun")
    """)
    main_cpp = textwrap.dedent("""
    #include "main.h"
    int main() {
        hello();
        return 0;
    }
    """)
    main_h = textwrap.dedent("""
        void hello();
    """)
    c.save({"consumer/conanfile.py": consumer,
            "consumer/CMakeLists.txt": cml,
            "consumer/main.cpp": main_cpp,
            "consumer/main.h": main_h})

    c.run(f"build consumer")
    assert "Hello, world!" in c.out
    # Check content of the generated files
    c.run(f"install --requires=hello/1.0 -g=CMakeConfigDeps")
    cmake = c.load("hello-Targets-release.cmake")
    assert "add_library(hello::hello INTERFACE IMPORTED)" in cmake
    assert "set_property(TARGET hello::hello APPEND PROPERTY INTERFACE_SOURCES\n"\
           "             $<$<CONFIG:RELEASE>:${hello_PACKAGE_FOLDER_RELEASE}/src/hello.cpp>)" in cmake
