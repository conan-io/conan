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
from conan.tools.cmake import CMake
from conan.tools.layout import cmake_layout


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
    assert "hello link libraries: hello::hello" in client.out

