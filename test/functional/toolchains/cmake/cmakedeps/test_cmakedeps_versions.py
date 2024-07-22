import os
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def hello_client():
    client = TestClient()
    client.run("new cmake_lib -d name=hello -d version=1.1")
    client.run("create . -tf=\"\"")
    return client


@pytest.mark.parametrize("name, version, params, cmake_fails, package_found", [
    ("hello", "1.0", "", False, True),
    ("Hello", "1.0", "", False, True),
    ("HELLO", "1.0", "", False, True),
    ("hello", "1.1", "", False, True),
    ("hello", "1.2", "", False, False),
    ("hello", "1.0", "EXACT", False, False),
    ("hello", "1.1", "EXACT", False, True),
    ("hello", "1.2", "EXACT", False, False),
    ("hello", "0.1", "", False, False),
    ("hello", "2.0", "", False, False),
    ("hello", "1.0", "REQUIRED", False, True),
    ("hello", "1.1", "REQUIRED", False, True),
    ("hello", "1.2", "REQUIRED", True, False),
    ("hello", "1.0", "EXACT REQUIRED", True, False),
    ("hello", "1.1", "EXACT REQUIRED", False, True),
    ("hello", "1.2", "EXACT REQUIRED", True, False),
    ("hello", "0.1", "REQUIRED", True, False),
    ("hello", "2.0", "REQUIRED", True, False)
])
@pytest.mark.tool("cmake")
def test_version(hello_client, name, version, params, cmake_fails, package_found):
    client = hello_client
    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(consumer NONE)
        find_package({name} {version} {params})
        message(STATUS "hello found: ${{{name}_FOUND}}")
        """).format(name=name, version=version, params=params)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            requires = "hello/1.1"
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("install .")
    exit_code = client.run("build .", assert_error=cmake_fails)
    if cmake_fails:
        assert exit_code != 0
    elif package_found:
        assert "hello found: 1" in client.out
    else:
        assert "hello found: 0" in client.out


@pytest.mark.tool("cmake")
def test_no_version_file(hello_client):
    client = hello_client

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.1)
        project(consumer NONE)
        find_package(hello 1.0 REQUIRED)
        message(STATUS "hello found: ${{hello_FOUND}}")
        """)

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class Conan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            requires = "hello/1.1"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
        """)

    client.save({"conanfile.py": conanfile, "CMakeLists.txt": cmakelists}, clean_first=True)
    client.run("install .")
    os.unlink(os.path.join(client.current_folder, "hello-config-version.cmake"))
    exit_code = client.run("build .", assert_error=True)
    assert 0 != exit_code
