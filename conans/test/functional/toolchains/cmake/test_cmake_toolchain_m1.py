import textwrap
import platform


import pytest

from conans.test.assets.cmake import gen_cmakelists
from conans.test.assets.sources import gen_function_cpp
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.parametrize("op_system", ["Macos", "iOS"])
def test_m1(op_system):
    os_version = "os.version=12.0" if op_system == "iOS" else ""
    os_sdk = "" if op_system == "Macos" else "os.sdk=iphoneos"
    profile = textwrap.dedent("""
        include(default)
        [settings]
        os={}
        {}
        {}
        arch=armv8
    """.format(op_system, os_sdk, os_version))

    client = TestClient(path_with_spaces=False)
    client.save({"m1": profile}, clean_first=True)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("create . --profile:build=default --profile:host=m1 -tf None")

    main = gen_function_cpp(name="main", includes=["hello"], calls=["hello"])
    cmakelists = gen_cmakelists(find_package=["hello"], appname="main", appsources=["main.cpp"])

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeDeps", "CMakeToolchain"

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
        """)

    client.save({"conanfile.py": conanfile,
                 "CMakeLists.txt": cmakelists,
                 "main.cpp": main,
                 "m1": profile}, clean_first=True)
    client.run("install . --profile:build=default --profile:host=m1")
    client.run("build .")
    main_path = "./main.app/main" if op_system == "iOS" else "./main"
    client.run_command(main_path, assert_error=True)
    assert "Bad CPU type in executable" in client.out
    client.run_command("lipo -info {}".format(main_path))
    assert "Non-fat file" in client.out
    assert "is architecture: arm64" in client.out
