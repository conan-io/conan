import platform
import textwrap

import pytest
from jinja2 import Template

from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.assets.sources import gen_function_h, gen_function_cpp
from conans.test.utils.tools import TestClient


def test_complete():
    """
    creates a multi-component package with 2 components "hello" and "bye
    """
    _function_h = textwrap.dedent(r"""
        #pragma once
        #include <iostream>

        {% for it in includes -%}
        #include "{{it}}.h"
        {%- endfor %}

        void {{name}}(){ std::cout << "{{name}}\n";}
        """)
    hello_h = Template(_function_h).render(name="hello")
    bye_h = Template(_function_h).render(name="bye")

    greetings = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake
        from conan.tools.files import copy

        class GreetingsConan(ConanFile):
            name = "greetings"
            version = "0.1"
            exports_sources = "src/*"

            def package(self):
                copy(self, "hello.h", dst=os.path.join(self.package_folder, "hello"), src="src")
                copy(self, "bye.h", dst=os.path.join(self.package_folder, "bye"), src="src")

            def package_info(self):
                self.cpp_info.components["hello"].includedirs = ["hello"]
                self.cpp_info.components["bye"].includedirs = ["bye"]
        """)

    test_package_greetings = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake

        class GreetingsTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            requires = "greetings/0.1"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def test(self):
                path = "{}".format(self.settings.build_type) if self.settings.os == "Windows" else "."
                self.run("{}{}example".format(path, os.sep))
        """)
    test_package_greetings_cpp = gen_function_cpp(name="main", includes=["hello", "bye"],
                                                  calls=["hello", "bye"])

    test_package_greetings_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

        find_package(greetings)

        add_executable(example example.cpp)
        target_link_libraries(example greetings::greetings)
        """)

    client = TestClient()
    client.save({"conanfile.py": greetings,
                 "src/hello.h": hello_h,
                 "src/bye.h": bye_h,
                 "test_package/conanfile.py": test_package_greetings,
                 "test_package/example.cpp": test_package_greetings_cpp,
                 "test_package/CMakeLists.txt": test_package_greetings_cmakelists})
    client.run("create . -s build_type=Release")
    print(client.out)
    assert "hello: Release!" in client.out
    assert "bye: Release!" in client.out
    client.run("create . -s build_type=Debug")
    assert "hello: Debug!" in client.out
    assert "bye: Debug!" in client.out
    return client
