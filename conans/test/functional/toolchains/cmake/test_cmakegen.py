import textwrap

from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


def test_cmakegen():
    client = TestClient()
    client.run("new hello/0.1 -s")
    client.run("create .")

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
            generators = "CMakeGen"

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
