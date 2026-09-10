import os
import platform
import re
import textwrap

import pytest

from conan.tools.files import replace_in_file
from conan.test.utils.mocks import ConanFileMock

from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.mark.skipif(platform.system() != "Linux", reason="No OS specific test")
@pytest.mark.tool("cmake", "3.27")
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
@pytest.mark.tool("cmake", "3.27")
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


@pytest.mark.skipif(platform.system() != "Linux", reason="No OS specific test")
@pytest.mark.tool("cmake", "3.27")
def test_cpp_info_sources_only_package():
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
                # Only sources is defined, the target is still created
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
    cmake = c.load("consumer/build/Release/generators/hello-Targets-release.cmake")
    assert "add_library(hello::hello INTERFACE IMPORTED)" in cmake
    assert "set_property(TARGET hello::hello APPEND PROPERTY INTERFACE_SOURCES\n"\
           "             $<$<CONFIG:RELEASE>:${hello_PACKAGE_FOLDER_RELEASE}/src/hello.cpp>)" in cmake

    # Now check a *transitive* dependency on "hello" (via "middle"): "middle" requires "hello"
    # directly, "transitive_consumer" only requires "middle", so "hello" is transitive to it.
    transitive_cml = textwrap.dedent("""
    set(CMAKE_CXX_COMPILER_WORKS 1)
    set(CMAKE_CXX_ABI_COMPILED 1)
    cmake_minimum_required(VERSION 3.15)
    project(example CXX)
    add_executable(example main.cpp)

    find_package(middle REQUIRED CONFIG)
    target_link_libraries(example middle::middle)
    """)
    transitive_consumer = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain, CMakeConfigDeps, cmake_layout
    class TransitiveConsumer(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "CMakeConfigDeps", "CMakeToolchain"
        requires = "middle/1.0"

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            self.run(os.path.join(self.cpp.build.bindir, "example"), env="conanrun")
    """)
    transitive_main_cpp = textwrap.dedent("""
    int main() {
        return 0;
    }
    """)
    c.save({"transitive_consumer/conanfile.py": transitive_consumer,
            "transitive_consumer/CMakeLists.txt": transitive_cml,
            "transitive_consumer/main.cpp": transitive_main_cpp})

    # 1) With default traits, "hello" contributes nothing to "middle" consumers (no headers,
    #    no libs - .sources does not count for this), so Conan skips it completely: its binary
    #    is not even fetched and its CMakeConfigDeps files are not generated at all
    middle = textwrap.dedent("""
        from conan import ConanFile
        class Middle(ConanFile):
            name = "middle"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"
            requires = "hello/1.0"

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.requires = ["hello::hello"]
    """)
    c.save({"middle/conanfile.py": middle})
    c.run("create middle")

    c.run("build transitive_consumer -c tools.compilation:verbosity=verbose")
    assert re.search(r"Skipped binaries(\s*)hello/1.0", c.out)
    assert "hello.cpp" not in c.out
    generators_folder = os.path.join(c.current_folder, "transitive_consumer", "build", "Release",
                                     "generators")
    assert not os.path.exists(os.path.join(generators_folder, "hello-Targets-release.cmake"))

    # 2) Force "hello" to remain transitively visible (not skipped), so its CMakeConfigDeps
    #    files ARE generated this time, and check that its sources still do not propagate
    middle = textwrap.dedent("""
        from conan import ConanFile
        class Middle(ConanFile):
            name = "middle"
            version = "1.0"
            settings = "os", "compiler", "build_type", "arch"

            def requirements(self):
                self.requires("hello/1.0", transitive_headers=True, transitive_libs=True)

            def package_info(self):
                self.cpp_info.includedirs = []
                self.cpp_info.requires = ["hello::hello"]
    """)
    c.save({"middle/conanfile.py": middle})
    c.run("create middle")

    c.run("build transitive_consumer -c tools.compilation:verbosity=verbose")
    assert "Skipped binaries" not in c.out
    assert "hello.cpp" not in c.out
    cmake = c.load("transitive_consumer/build/Release/generators/hello-Targets-release.cmake")
    assert "add_library(hello::hello INTERFACE IMPORTED)" in cmake
    assert "INTERFACE_SOURCES" not in cmake
