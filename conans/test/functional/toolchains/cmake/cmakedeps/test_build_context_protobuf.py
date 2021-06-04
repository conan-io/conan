import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture
def client():
    c = TestClient()
    conanfile = textwrap.dedent('''
    from conans import ConanFile
    from conans.tools import save, chdir
    import os

    class Protobuf(ConanFile):
        settings = "build_type", "os", "arch", "compiler"

        def package(self):
            my_cmake_module = """
                  function(foo_generate)
                     write_file(foo_generated.h "int from_context = %s;")
                  endfunction()
            """

            with chdir(self.package_folder):
                save("include_build/protobuf.h", "int protubuff_stuff(){ return 1; }")
                save("include_host/protobuf.h", "int protubuff_stuff(){ return 2; }")
                save("build/my_tools_build.cmake", my_cmake_module % "1")
                save("build/my_tools_host.cmake", my_cmake_module % "2")

        def package_info(self):
            # This info depends on self.context !!
            self.cpp_info.includedirs = ["include_{}".format(self.context)]
            path_build_modules = os.path.join("build", "my_tools_{}.cmake".format(self.context))
            self.cpp_info.set_property("cmake_build_modules", [path_build_modules])

    ''')
    c.save({"conanfile.py": conanfile})
    c.run("create . protobuf/1.0@")
    return c


main = textwrap.dedent("""
    #include <iostream>
    #include "protobuf.h"
    #include "foo_generated.h"


    int main(){
        int ret = protubuff_stuff();

        if(ret == 1){
            std::cout << " Library from build context!" << std::endl;
        }
        else if(ret == 2){
            std::cout << " Library from host context!" << std::endl;
        }

        // Variable declared at the foo_generated
        if(from_context == 1){
            std::cout << " Generated code in build context!" << std::endl;
        }
        else if(from_context == 2){
            std::cout << " Generated code in host context!" << std::endl;
        }
        return 0;
    }
    """)

consumer_conanfile = textwrap.dedent("""
    import os
    from conans import ConanFile
    from conan.tools.cmake import CMake, CMakeToolchain, CMakeDeps

    class Consumer(ConanFile):
        settings = "build_type", "os", "arch", "compiler"
        exports_sources = "CMakeLists.txt", "main.cpp"
        requires = "protobuf/1.0"
        build_requires = "protobuf/1.0"

        def generate(self):
            toolchain = CMakeToolchain(self)
            toolchain.generate()

            deps = CMakeDeps(self)
            {}
            deps.generate()

        def build(self):
            cmake = CMake(self)
            cmake.configure()
            cmake.build()
            folder = str(self.settings.build_type) if self.settings.os == "Windows" else "."
            self.run(os.sep.join([folder, "app"]))
    """)


def test_build_modules_from_build_context(client):
    consumer_cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(protobuf)
        find_package(protobuf_BUILD)
        add_executable(app main.cpp)
        foo_generate()
        target_link_libraries(app protobuf::protobuf)
        """)

    cmake_deps_conf = """
        deps.build_context_activated = ["protobuf"]
        deps.build_context_build_modules = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
    """

    client.save({"conanfile.py": consumer_conanfile.format(cmake_deps_conf),
                 "CMakeLists.txt": consumer_cmake,
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default")
    assert "Library from host context!" in client.out
    assert "Generated code in build context!" in client.out


def test_build_modules_and_target_from_build_context(client):
    consumer_cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(protobuf)
        find_package(protobuf_BUILD)
        add_executable(app main.cpp)
        foo_generate()
        target_link_libraries(app protobuf_BUILD::protobuf_BUILD)
        """)

    cmake_deps_conf = """
        deps.build_context_activated = ["protobuf"]
        deps.build_context_build_modules = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
    """

    client.save({"conanfile.py": consumer_conanfile.format(cmake_deps_conf),
                 "CMakeLists.txt": consumer_cmake,
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default")
    assert "Library from build context!" in client.out
    assert "Generated code in build context!" in client.out


def test_build_modules_from_host_and_target_from_build_context(client):
    consumer_cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(protobuf)
        find_package(protobuf_BUILD)
        add_executable(app main.cpp)
        foo_generate()
        target_link_libraries(app protobuf_BUILD::protobuf_BUILD)
        """)

    cmake_deps_conf = """
        deps.build_context_activated = ["protobuf"]
        deps.build_context_suffix = {"protobuf": "_BUILD"}
    """

    client.save({"conanfile.py": consumer_conanfile.format(cmake_deps_conf),
                 "CMakeLists.txt": consumer_cmake,
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default")
    assert "Library from build context!" in client.out
    assert "Generated code in host context!" in client.out


def test_build_modules_and_target_from_host_context(client):
    consumer_cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(protobuf)
        find_package(protobuf_BUILD)
        add_executable(app main.cpp)
        foo_generate()
        target_link_libraries(app protobuf::protobuf)
        """)

    cmake_deps_conf = """
        deps.build_context_activated = ["protobuf"]
        deps.build_context_build_modules = []
        deps.build_context_suffix = {"protobuf": "_BUILD"}
    """

    client.save({"conanfile.py": consumer_conanfile.format(cmake_deps_conf),
                 "CMakeLists.txt": consumer_cmake,
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default")
    assert "Conan: Target declared 'protobuf::protobuf'" in client.out
    assert "Conan: Target declared 'protobuf_BUILD::protobuf_BUILD'" in client.out
    assert "Library from host context!" in client.out
    assert "Generated code in host context!" in client.out


def test_exception_when_not_prefix_specified(client):
    cmake_deps_conf = """
        deps.build_context_activated = ["protobuf"]
    """
    client.save({"conanfile.py": consumer_conanfile.format(cmake_deps_conf),
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default", assert_error=True)
    assert "The package 'protobuf' exists both as 'require' and as 'build require'. " \
           "You need to specify a suffix using the 'build_context_suffix' attribute at the " \
           "CMakeDeps generator." in client.out


def test_not_activated_not_fail(client):
    consumer_cmake = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(protobuf)
        add_executable(app main.cpp)
        foo_generate()
        target_link_libraries(app protobuf::protobuf)
        """)

    client.save({"conanfile.py": consumer_conanfile.format(""),
                 "CMakeLists.txt": consumer_cmake,
                 "main.cpp": main})

    client.run("create . app/1.0@ -pr:b default -pr:h default")
    assert "app/1.0: Created package" in client.out
    assert "Library from host context!" in client.out
    assert "Generated code in host context!" in client.out
