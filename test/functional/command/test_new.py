import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_conan_new_compiles():
    # TODO: Maybe add more templates that are not used in the rest of the test suite?
    tc = TestClient()
    tc.run("new header_lib -d name=hello -d version=1.0 -o=hello")
    tc.run("new header_lib -d name=bye -d version=1.0 -d requires=hello/1.0 -o=bye")

    tc.run("create hello -tf=")
    tc.run("create bye")


@pytest.mark.tool("cmake")
def test_conan_new_empty():
    c = TestClient()
    c.run("new")
    cmakelists = textwrap.dedent("""
    cmake_minimum_required(VERSION 3.15)
    project(PackageTest CXX)
    add_executable(example main.cpp)
    """)
    main = textwrap.dedent(r"""
    #include <iostream>

    int main() {
        std::cout << "Hello World!\n";
    }
    """)
    c.save({
        "CMakeLists.txt": cmakelists,
        "main.cpp": main,
    })
    c.run("build")
    suffix = ".exe" if platform.system() == "Windows" else ""
    assert os.path.exists(os.path.join(c.current_folder, "build", "Release", f"example{suffix}"))
