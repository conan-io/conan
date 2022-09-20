import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


def test_cmake_virtualenv():
    client = TestClient()
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("create . -tf=None")

    cmakewrapper = textwrap.dedent(r"""
        from conans import ConanFile
        import os
        from conans.tools import save, chdir
        class Pkg(ConanFile):
            def package(self):
                with chdir(self.package_folder):
                    save("cmake.bat", "@echo off\necho MYCMAKE WRAPPER!!\ncmake.exe %*")
                    save("cmake.sh", 'echo MYCMAKE WRAPPER!!\ncmake "$@"')
                    os.chmod("cmake.sh", 0o777)

            def package_info(self):
                # Custom buildenv not defined by cpp_info
                self.buildenv_info.prepend_path("PATH", self.package_folder)
            """)
    consumer = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake
        class App(ConanFile):
            settings = "os", "arch", "compiler", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            requires = "hello/0.1"
            build_requires = "cmakewrapper/0.1"
            generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv"
            apply_env = False

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

        find_package(hello)
        add_executable(app main.cpp)
        target_link_libraries(app hello::hello)
        """)

    client.save({"cmakewrapper/conanfile.py": cmakewrapper,
                 "consumer/conanfile.py": consumer,
                 "consumer/main.cpp": gen_function_cpp(name="main", includes=["hello"],
                                                       calls=["hello"]),
                 "consumer/CMakeLists.txt": cmakelists},
                clean_first=True)

    client.run("create cmakewrapper cmakewrapper/0.1@")
    client.run("create consumer consumer/0.1@")
    assert "MYCMAKE WRAPPER!!" in client.out
    assert "consumer/0.1: Created package" in client.out


def test_complete():
    client = TestClient()
    client.run("new myopenssl/1.0 -m=cmake_lib")
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
            generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv"
            exports = "*"
            apply_env = False

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def package(self):
                src = str(self.settings.build_type) if self.settings.os == "Windows" else ""
                self.copy("mycmake*", src=src, dst="bin")

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
            generators = "CMakeDeps", "CMakeToolchain", "VirtualBuildEnv", "VirtualRunEnv"
            apply_env = False

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

    client.run("create . myapp/0.1@ -s:b build_type=Release -s:h build_type=Debug")
    first, last = str(client.out).split("RUNNING MYAPP")
    assert "mycmake: Release!" in first
    assert "myopenssl/1.0: Hello World Release!" in first

    assert "myapp: Debug!" in last
    assert "myopenssl/1.0: Hello World Debug!" in last
