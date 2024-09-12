import textwrap

import pytest

from conan.test.assets.sources import gen_function_cpp
from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_cmake_virtualenv(matrix_client):
    client = matrix_client

    cmakewrapper = textwrap.dedent(r"""
        from conan import ConanFile
        import os
        from conan.tools.files import save, chdir
        class Pkg(ConanFile):
            def package(self):
                with chdir(self, self.package_folder):
                    save(self, "cmake.bat", "@echo off\necho MYCMAKE WRAPPER!!\ncmake.exe %*")
                    save(self, "cmake.sh", 'echo MYCMAKE WRAPPER!!\ncmake "$@"')
                    os.chmod("cmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
            """)
    consumer = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            requires = "matrix/1.0"
            build_requires = "cmakewrapper/0.1"
            generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv"

            def build(self):
                cmake = CMake(self)
                if self.settings.os != "Windows":
                    cmake._cmake_program = "cmake.sh"  # VERY DIRTY HACK
                cmake.configure()
                cmake.build()
        """)

    cmakelists = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.15)
        project(MyApp CXX)

        find_package(matrix)
        add_executable(app main.cpp)
        target_link_libraries(app matrix::matrix)
        """)

    client.save({"cmakewrapper/conanfile.py": cmakewrapper,
                 "consumer/conanfile.py": consumer,
                 "consumer/main.cpp": gen_function_cpp(name="main", includes=["matrix"],
                                                       calls=["matrix"]),
                 "consumer/CMakeLists.txt": cmakelists},
                clean_first=True)

    client.run("create cmakewrapper --name=cmakewrapper --version=0.1")
    client.run("create consumer --name=consumer --version=0.1")
    assert "MYCMAKE WRAPPER!!" in client.out
    assert "consumer/0.1: Created package" in client.out


@pytest.mark.tool("cmake")
def test_complete():
    client = TestClient()
    client.run("new cmake_lib -d name=myopenssl -d version=1.0")
    client.run("create . -o myopenssl/*:shared=True")
    client.run("create . -o myopenssl/*:shared=True -s build_type=Debug")

    mycmake_main = gen_function_cpp(name="main", msg="mycmake",
                                    includes=["myopenssl"], calls=["myopenssl"])
    mycmake_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake
        from conan.tools.files import copy
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            requires = "myopenssl/1.0"
            default_options = {"myopenssl:shared": True}
            generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv"
            exports_sources = "*"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                src = str(self.settings.build_type) if self.settings.os == "Windows" else ""
                copy(self, "mycmake*", os.path.join(self.source_folder, src),
                     os.path.join(self.package_folder, "bin"))

            def package_info(self):
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
    client.run("create . --name=mycmake --version=1.0", assert_error=True)
    assert "The usage of package names `myopenssl:shared` in options is deprecated, " \
           "use a pattern like `myopenssl/*:shared` instead" in client.out

    # Fix the default options and repeat the create
    fixed_cf = mycmake_conanfile.replace('default_options = {"myopenssl:shared": True}',
                                         'default_options = {"myopenssl*:shared": True}')
    client.save({"conanfile.py": fixed_cf})
    client.run("create . --name=mycmake --version=1.0")

    mylib = textwrap.dedent(r"""
        from conan import ConanFile
        import os
        from conan.tools.cmake import CMake
        class Pkg(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            build_requires = "mycmake/1.0"
            requires = "myopenssl/1.0"
            default_options = {"myopenssl/*:shared": True}
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run("mycmake")
                self.output.info("RUNNING MYAPP")
                if self.settings.os == "Windows":
                    self.run(os.sep.join([".", str(self.settings.build_type), "myapp"]),
                             env="conanrun")
                else:
                    self.run(os.sep.join([".", "myapp"]), env=["conanrun"])
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

    client.run("create . --name=myapp --version=0.1 -s:b build_type=Release -s:h build_type=Debug")
    first, last = str(client.out).split("RUNNING MYAPP")
    assert "mycmake: Release!" in first
    assert "myopenssl/1.0: Hello World Release!" in first

    assert "myapp: Debug!" in last
    assert "myopenssl/1.0: Hello World Debug!" in last
