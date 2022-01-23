import os
import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
@pytest.mark.tool_cmake
def test_shared_link_flags():
    """
    Testing CMakeDeps and linker flags injection

    Issue: https://github.com/conan-io/conan/issues/9936
    """
    conanfile = textwrap.dedent("""
    from conans import ConanFile
    from conan.tools.cmake import CMake, cmake_layout


    class HelloConan(ConanFile):
        name = "hello"
        version = "1.0"
        settings = "os", "compiler", "build_type", "arch"
        options = {"shared": [True, False]}
        default_options = {"shared": False}
        exports_sources = "CMakeLists.txt", "src/*"
        generators = "CMakeDeps", "CMakeToolchain"

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
            self.cpp_info.libs = ["hello"]
            self.cpp_info.sharedlinkflags = ["-z now", "-z relro"]
            self.cpp_info.exelinkflags = ["-z now", "-z relro"]
    """)

    client = TestClient()
    client.run("new hello/1.0 -m cmake_lib")
    client.save({"conanfile.py": conanfile})
    client.run("create .")
    t = os.path.join("test_package", "cmake-build-release", "conan", "hello-release-x86_64-data.cmake")
    target_data_cmake_content = client.load(t)
    assert 'set(hello_SHARED_LINK_FLAGS_RELEASE "-z now;-z relro")' in target_data_cmake_content
    assert 'set(hello_EXE_LINK_FLAGS_RELEASE "-z now;-z relro")' in target_data_cmake_content
    assert "hello/1.0: Hello World Release!" in client.out
