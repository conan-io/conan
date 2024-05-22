import os
import shutil
import textwrap

from conan.test.assets.sources import gen_function_cpp, gen_function_h
from conan.test.utils.tools import TestClient


def test_editable_cmake_components():
    hello_h = gen_function_h(name="hello")
    hello_cpp = gen_function_cpp(name="hello", includes=["hello"])
    bye_h = gen_function_h(name="bye")
    bye_cpp = gen_function_cpp(name="bye", includes=["bye"])

    conanfile_greetings = textwrap.dedent("""
        from os.path import join
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        from conan.tools.files import copy

        class GreetingsConan(ConanFile):
            name = "greetings"
            version = "0.1"
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"
            exports_sources = "src/*"

            def build(self):
               cmake = CMake(self)
               cmake.configure()
               cmake.build()

            def layout(self):
                cmake_layout(self, src_folder="src")
                self.cpp.source.components["hello"].includedirs = ["."]
                self.cpp.source.components["bye"].includedirs = ["."]
                bt = "." if self.settings.os != "Windows" else str(self.settings.build_type)
                self.cpp.build.components["hello"].libdirs = [bt]
                self.cpp.build.components["bye"].libdirs = [bt]

            def package(self):
               copy(self, "*.h", src=self.source_folder,
                                 dst=join(self.package_folder, "include"))
               copy(self, "*.lib", src=self.build_folder,
                                   dst=join(self.package_folder, "lib"), keep_path=False)
               copy(self, "*.a", src=self.build_folder,
                                 dst=join(self.package_folder, "lib"), keep_path=False)

            def package_info(self):
               self.cpp_info.components["hello"].libs = ["hello"]
               self.cpp_info.components["bye"].libs = ["bye"]

               self.cpp_info.set_property("cmake_file_name", "MYG")
               self.cpp_info.set_property("cmake_target_name", "MyGreetings::MyGreetings")
               self.cpp_info.components["hello"].set_property("cmake_target_name", "MyGreetings::MyHello")
               self.cpp_info.components["bye"].set_property("cmake_target_name", "MyGreetings::MyBye")
           """)

    cmakelists_greetings = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(greetings CXX)

        add_library(hello hello.cpp)
        target_include_directories(hello PRIVATE hello)
        add_library(bye bye.cpp)
        target_include_directories(bye PRIVATE bye)
        """)

    app_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class GreetingsTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"

            def requirements(self):
                self.requires("greetings/0.1")

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run(os.path.join(self.cpp.build.bindirs[0], "example"))
                self.run(os.path.join(self.cpp.build.bindirs[0], "example2"))
            """)
    app_cpp = gen_function_cpp(name="main", includes=["hello/hello", "bye/bye"],
                               calls=["hello", "bye"])
    app_cpp2 = gen_function_cpp(name="main", includes=["hello/hello"], calls=["hello"])

    app_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.0)
        project(PackageTest CXX)

        find_package(MYG)

        add_executable(example example.cpp)
        target_link_libraries(example MyGreetings::MyGreetings)

        add_executable(example2 example2.cpp)
        target_link_libraries(example2 MyGreetings::MyHello)
        """)

    client = TestClient()
    client.save({"greetings/conanfile.py": conanfile_greetings,
                 "greetings/src/CMakeLists.txt": cmakelists_greetings,
                 "greetings/src/hello/hello.h": hello_h,
                 "greetings/src/hello.cpp": hello_cpp,
                 "greetings/src/bye/bye.h": bye_h,
                 "greetings/src/bye.cpp": bye_cpp,
                 "app/conanfile.py": app_conanfile,
                 "app/example.cpp": app_cpp,
                 "app/example2.cpp": app_cpp2,
                 "app/CMakeLists.txt": app_cmakelists})
    client.run("create greetings")
    client.run("build app")
    assert "hello: Release!" in client.out
    assert "bye: Release!" in client.out

    client.run("remove * -c")
    shutil.rmtree(os.path.join(client.current_folder, "app", "build"))
    client.run("editable add greetings")
    client.run("build greetings")
    client.run("build app")
    assert str(client.out).count("hello: Release!") == 2
    assert str(client.out).count("bye: Release!") == 1

    # Do a modification to one component, to verify it is used correctly
    bye_cpp = gen_function_cpp(name="bye", includes=["bye"], msg="Adios")
    client.save({"greetings/src/bye.cpp": bye_cpp})
    client.run("build greetings")
    client.run("build app")
    assert str(client.out).count("hello: Release!") == 2
    assert str(client.out).count("Adios: Release!") == 1
