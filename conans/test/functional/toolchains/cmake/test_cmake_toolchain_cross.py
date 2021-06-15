import textwrap
import platform


import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="Only Linux")
def test_cross_build():
    rpi_profile = textwrap.dedent("""
        [settings]
        os=Linux
        compiler=gcc
        compiler.version=6
        compiler.libcxx=libstdc++11
        arch=armv8
        build_type=Release

        [env]
        CXX=arm-linux-gnueabihf-g++
        CC=arm-linux-gnueabihf-gcc
        """)

    client = TestClient(path_with_spaces=False)
    print(client.current_folder)

    main = gen_function_cpp(name="main")
    cmakelists = gen_cmakelists(appname="main", appsources=["main.cpp"])
    cmakelists += 'message(STATUS "SYSTEM_PROCESSOR=${CMAKE_SYSTEM_PROCESSOR}")\n' \
                  'set(CMAKE_VERBOSE_MAKEFILE ON)'

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class TestConan(ConanFile):
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelists,
                 "main.cpp": main,
                 "rpi": rpi_profile})
    client.run("install . --profile:build=default --profile:host=rpi")
    client.run("build .")
    print(client.out)
    main_path = "./main"
    client.run_command(main_path, assert_error=True)
    assert "Bad CPU type in executable" in client.out
    client.run_command("lipo -info {}".format(main_path))
    assert "Non-fat file" in client.out
    assert "is architecture: arm64" in client.out
