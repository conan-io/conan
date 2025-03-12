import platform
import textwrap

import pytest

from conan.internal.model.pkg_type import PackageType
from conan.test.utils.tools import TestClient

new_value = "will_break_next"


@pytest.mark.parametrize("shared", [True, False])
# @pytest.mark.tool("cmake")
@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
def test_osx_frameworks(shared):
    """
    Testing custom package frameworks + system frameworks + requirements
    """
    client = TestClient()
    # dep/1.0
    client.run("new cmake_lib -d name=dep -d version=1.0")
    client.run(f"create . -tf='' -o '&:shared={shared}'")
    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(MyLib CXX)

    find_package(dep CONFIG REQUIRED)

    add_library(mylib src/mylib.cpp)
    target_include_directories(mylib PUBLIC include)
    target_link_libraries(mylib dep::dep)

    set_target_properties(mylib PROPERTIES PUBLIC_HEADER "include/mylib.h")

    install(TARGETS mylib)
    """)
    mylib_cpp = textwrap.dedent("""
    #include "mylib.h"
    #include "dep.h"
    #include <iostream>

    void greet() {
        // MyLib
        std::cout << "Hello from MyLib!" << std::endl;

        // dep requirement
        dep();
    }
    """)
    mylib_h = textwrap.dedent("""
    #pragma once
    #include <vector>
    #include <string>
    void greet();
    """)
    conanfile = textwrap.dedent(f"""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout

    class MyLib(ConanFile):
        name = "mylib"
        version = "1.0"
        settings = "os", "arch", "compiler", "build_type"
        languages = ["C++"]
        package_type = "{'static-library' if shared else 'shared-library'}"
        exports_sources = "CMakeLists.txt", "src/*", "include/*"
        generators = "CMakeToolchain", "CMakeConfigDeps"
        requires = "dep/1.0"

        def layout(self):
            cmake_layout(self)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def package(self):
            cmake = CMake(self)
            cmake.install()

        def package_info(self):
            self.cpp_info.libs = ["mylib"]
    """)
    test_main_cpp = textwrap.dedent("""
    #include <mylib.h>
    int main() {
        greet();
    }
    """)
    test_conanfile = textwrap.dedent("""
    import os
    from conan import ConanFile
    from conan.tools.cmake import CMake, cmake_layout
    from conan.tools.build import can_run

    class LibTestConan(ConanFile):
        settings = "os", "compiler", "build_type", "arch"
        generators = "CMakeConfigDeps", "CMakeToolchain"

        def requirements(self):
            self.requires(self.tested_reference_str)

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()

        def layout(self):
            cmake_layout(self)

        def test(self):
            if can_run(self):
                cmd = os.path.join(self.cpp.build.bindir, "example")
                self.run(cmd, env="conanrun")
    """)
    test_cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)
    find_package(mylib CONFIG REQUIRED)
    add_executable(example main.cpp)
    target_link_libraries(example mylib::mylib)
    """)
    client.save({
        'test_package/main.cpp': test_main_cpp,
        'test_package/CMakeLists.txt': test_cmakelists,
        'test_package/conanfile.py': test_conanfile,
        'CMakeLists.txt': cmakelists,
        'src/mylib.cpp': mylib_cpp,
        'include/mylib.h': mylib_h,
        'conanfile.py': conanfile
    }, clean_first=True)
    client.run(f"create . -c tools.cmake.cmakedeps:new={new_value} -o '*:shared={shared}'")

    assert "Hello from MyLib!" in client.out
    assert "dep/1.0: Hello World" in client.out
