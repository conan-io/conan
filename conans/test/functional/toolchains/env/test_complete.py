import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


def test_complete():
    client = TestClient()
    client.run("new myopenssl/1.0 -m=v2_cmake")
    client.run("create . -o myopenssl:shared=True")
    client.run("create . -o myopenssl:shared=True -s build_type=Debug")

    mycmake_main = gen_function_cpp(name="main", msg="mycmake",
                                    includes=["myopenssl"], calls=["myopenssl"])
    mycmake_conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "myopenssl/1.0"
            default_options = {"myopenssl:shared": True}
            generators = "CMakeGen"
            exports = "*"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                src = str(self.settings.build_type) if self.settings.os == "Windows" else ""
                self.copy("mycmake*", src=src, dst="bin")

            def package_info(self):
                self.cpp_info.exes = ["mycmake"]
                self.cpp_info.bindirs = ["bin"]
        """)
    mycmake_cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyCmake CXX)

        find_package(myopenssl REQUIRED)
        add_executable(mycmake main.cpp)
        target_link_libraries(mycmake PRIVATE myopenssl::myopenssl)
        """)
    client.save({"conanfile.py": mycmake_conanfile,
                 "CMakeLists.txt": mycmake_cmakelists,
                 "main.cpp": mycmake_main}, clean_first=True)
    client.run("create . mycmake/1.0@")

    mylib = textwrap.dedent(r"""
        from conans import ConanFile
        import os
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "mycmake/1.0"
            requires = "myopenssl/1.0"
            default_options = {"myopenssl:shared": True}
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeGen"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run("mycmake")
                self.output.info("RUNNING MYAPP")
                if self.settings.os == "Windows":
                    self.run(os.sep.join([".", str(self.settings.build_type), "myapp"]),
                             env="conanrunenv")
                else:
                    self.run(os.sep.join([".", "myapp"]), env="conanrunenv")
            """)

    cmakelists = textwrap.dedent("""
        set(CMAKE_CXX_COMPILER_WORKS 1)
        set(CMAKE_CXX_ABI_COMPILED 1)
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(myopenssl)
        add_executable(myapp main.cpp)
        target_link_libraries(myapp myopenssl::myopenssl)
        """)

    client.save({"conanfile.py": mylib,
                 "main.cpp": gen_function_cpp(name="main", msg="myapp", includes=["myopenssl"],
                                              calls=["myopenssl"]),
                 "CMakeLists.txt": cmakelists},
                clean_first=True)

    client.run("create . myapp/0.1@ -s:b build_type=Release -s:h build_type=Debug")
    first, last = str(client.out).split("RUNNING MYAPP")
    assert "mycmake: Release!" in first
    assert "myopenssl/1.0: Hello World Release!" in first

    assert "myapp: Debug!" in last
    assert "myopenssl/1.0: Hello World Debug!" in last
