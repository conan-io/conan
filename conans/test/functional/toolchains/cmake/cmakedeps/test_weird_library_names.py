import textwrap

import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def client_weird_lib_name():
    c = TestClient()
    conanfile = textwrap.dedent("""
        import os, platform
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

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
                self.copy("*.h", dst="include", src="src")
                self.copy("*.lib", dst="lib", keep_path=False)
                self.copy("*.a", dst="lib", keep_path=False)
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
    c.run("create . hello/0.1@")
    return c


@pytest.mark.tool_cmake
def test_cmakedeps(client_weird_lib_name):
    c = client_weird_lib_name
    c.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]), clean_first=True)
    c.run("create . chat/0.1@")
    assert "chat/0.1: Created package" in c.out


# TODO: Remove in Conan 2.0
@pytest.mark.tool_cmake
def test_cmake_find_package(client_weird_lib_name):
    c = client_weird_lib_name
    files = pkg_cmake("chat", "0.1", requires=["hello/0.1"])
    conanfile = textwrap.dedent("""
        import os, platform
        from conans import ConanFile, CMake

        class Pkg(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            settings = "os", "compiler", "arch", "build_type"
            generators = "cmake_find_package"
            requires = "hello/0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    files["conanfile.py"] = conanfile
    c.save(files, clean_first=True)
    c.run("create . chat/0.1@")
    assert "chat/0.1: Created package" in c.out


# TODO: Remove in Conan 2.0
@pytest.mark.tool_cmake
def test_cmake_find_package_multi(client_weird_lib_name):
    c = client_weird_lib_name
    files = pkg_cmake("chat", "0.1", requires=["hello/0.1"])
    conanfile = textwrap.dedent("""
        import os, platform
        from conans import ConanFile, CMake

        class Pkg(ConanFile):
            exports_sources = "CMakeLists.txt", "src/*", "include/*"
            settings = "os", "compiler", "arch", "build_type"
            generators = "cmake_find_package_multi"
            requires = "hello/0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)
    files["conanfile.py"] = conanfile
    c.save(files, clean_first=True)
    c.run("create . chat/0.1@")
    assert "chat/0.1: Created package" in c.out
