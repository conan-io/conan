import os
import textwrap

from conans import load
from conans.test.utils.tools import TestClient


def test_macros_with_components_inclusion():
    t = TestClient()
    conanfile = textwrap.dedent("""
               from conans import ConanFile
               from conan.tools.cmake import CMakeDeps
               class MyLib(ConanFile):

                   settings = "os", "arch", "compiler", "build_type"

                   def package_info(self):
                       self.cpp_info.components["component1"].libs = ["foo"]
               """)
    t.save({"conanfile.py": conanfile})
    t.run("create . mylib/1.0@")

    conanfile = textwrap.dedent("""
           from conans import ConanFile
           from conan.tools.cmake import CMakeDeps
           class App(ConanFile):
               settings = "os", "arch", "compiler", "build_type"
               requires = "mylib/1.0"

               def generate(self):
                   cmake = CMakeDeps(self)
                   cmake.generate()

           """)

    t.save({"conanfile.py": conanfile})
    t.run("install .")
    contents = load(os.path.join(t.current_folder, "mylibTarget-release.cmake"))
    assert "include(${CMAKE_CURRENT_LIST_DIR}/cmakedeps_macros.cmake)" in contents
