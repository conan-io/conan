import textwrap

import pytest

from conan.test.assets.cmake import gen_cmakelists
from conan.test.assets.pkg_cmake import pkg_cmake
from conan.test.assets.sources import gen_function_h, gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client_weird_lib_name():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os, platform
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        from conan.tools.files import copy

        class Pkg(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*"
            settings = "os", "compiler", "arch", "build_type"
            generators = "CMakeToolchain", "CMakeDeps"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                copy(self, "*.h", os.path.join(self.source_folder, "src"),
                                  os.path.join(self.package_folder, "include"))
                copy(self, "*.lib", self.build_folder, os.path.join(self.package_folder, "lib"),
                     keep_path=False)
                copy(self, "*.a", self.build_folder, os.path.join(self.package_folder, "lib"),
                     keep_path=False)
                ext = "a" if platform.system() != "Windows" else "lib"
                prefix = "lib" if platform.system() != "Windows" else ""
                os.chdir(os.path.join(self.package_folder, "lib"))
                os.rename("{}hello_0.1.{}".format(prefix, ext),
                          "{}he!llo@0.1.{}".format(prefix, ext))

            def package_info(self):
                self.cpp_info.libs = ["he!llo@0.1"]
            """)

    hdr = gen_function_h(name="hello")
    src = gen_function_cpp(name="hello")
    cmake = gen_cmakelists(libname="hello_0.1", libsources=["src/hello.cpp"])

    c.save({"src/hello.h": hdr,
            "src/hello.cpp": src,
            "CMakeLists.txt": cmake,
            "conanfile.py": conanfile})
    c.run("create . --name=hello --version=0.1")
    return c


@pytest.mark.tool("cmake")
def test_cmakedeps(client_weird_lib_name):
    c = client_weird_lib_name
    c.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]), clean_first=True)
    c.run("create . --name=chat --version=0.1")
    assert "chat/0.1: Created package" in c.out
