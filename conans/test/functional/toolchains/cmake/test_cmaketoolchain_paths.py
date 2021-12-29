import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake
@pytest.mark.parametrize("package", ["hello", "zlib"])
@pytest.mark.parametrize("find_package", ["module", "config"])
def test_cmaketoolchain_path_find(package, find_package):
    """Test with user "Hello" and also ZLIB one, to check that package ZLIB
    has priority over the CMake system one

    Also, that user cmake files in the root are accessible via CMake include()
    """
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            exports = "*"
            def layout(self):
                pass
            def package(self):
                self.copy(pattern="*", keep_path=False)
        """)
    find = textwrap.dedent("""
        SET({package}_FOUND 1)
        MESSAGE("HELLO FROM THE {package} FIND PACKAGE!")
        """).format(package=package)
    myowncmake = textwrap.dedent("""
        MESSAGE("MYOWNCMAKE FROM {package}!")
        """).format(package=package)

    filename = "{}Config.cmake" if find_package == "config" else "Find{}.cmake"
    filename = filename.format(package)
    client.save({"conanfile.py": conanfile,
                 "{}".format(filename): find,
                 "myowncmake.cmake": myowncmake})
    client.run("create . --name={} --version=0.1".format(package))

    consumer = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        project(MyHello CXX)
        cmake_minimum_required(VERSION 3.15)

        find_package({package} REQUIRED)
        include(myowncmake)
        """).format(package=package)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install --reference={}/0.1@ -g CMakeToolchain".format(package))
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared" not in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) in client.out
    assert "MYOWNCMAKE FROM {package}!".format(package=package) in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    # But it is still possible to include(owncmake)
    client.run("install --reference={}/0.1@ -g CMakeToolchain -g CMakeDeps".format(package))
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared '{package}::{package}'".format(package=package) in client.out
    assert "HELLO FROM THE {package} FIND PACKAGE!".format(package=package) not in client.out
    assert "MYOWNCMAKE FROM {package}!".format(package=package) in client.out


@pytest.mark.tool_cmake
def test_cmaketoolchain_path_find_real_config():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class TestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            exports = "*"
            generators = "CMakeToolchain"

            def layout(self):
                pass

            def build(self):
                cmake = CMake(self)
                cmake.configure()

            def package(self):
                cmake = CMake(self)
                cmake.install()
        """)
    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyHello NONE)

        add_library(hello INTERFACE)
        install(TARGETS hello EXPORT helloConfig)
        export(TARGETS hello
            NAMESPACE hello::
            FILE "${CMAKE_CURRENT_BINARY_DIR}/helloConfig.cmake"
        )
        install(EXPORT helloConfig
            DESTINATION "${CMAKE_INSTALL_PREFIX}/hello/cmake"
            NAMESPACE hello::
        )
        """)
    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmake})
    client.run("create . --name=hello --version=0.1")

    consumer = textwrap.dedent("""
        project(MyHello NONE)
        cmake_minimum_required(VERSION 3.15)

        find_package(hello REQUIRED)
        """)

    client.save({"CMakeLists.txt": consumer}, clean_first=True)
    client.run("install --reference=hello/0.1@ -g CMakeToolchain")
    with client.chdir("build"):
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    # If it didn't fail, it found the helloConfig.cmake
    assert "Conan: Target declared" not in client.out

    # If using the CMakeDeps generator, the in-package .cmake will be ignored
    # But it is still possible to include(owncmake)
    client.run("install --reference=hello/0.1@ -g CMakeToolchain -g CMakeDeps")
    with client.chdir("build2"):  # A clean folder, not the previous one, CMake cache doesnt affect
        client.run_command("cmake .. -DCMAKE_TOOLCHAIN_FILE=../conan_toolchain.cmake")
    assert "Conan: Target declared 'hello::hello'" in client.out

