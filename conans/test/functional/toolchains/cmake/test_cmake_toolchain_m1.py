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
    custom_content = 'message("CMAKE_SYSTEM_NAME: ${CMAKE_SYSTEM_NAME}") \n' \
                     'message("CMAKE_SYSTEM_PROCESSOR: ${CMAKE_SYSTEM_PROCESSOR}") \n'
    cmakelists = gen_cmakelists(find_package=["hello"], appname="main", appsources=["main.cpp"],
                                custom_content=custom_content)

    conanfile = textwrap.dedent("""
        from conans import ConanFile
        from conan.tools.cmake import CMake, cmake_layout

        class TestConan(ConanFile):
            requires = "hello/0.1"
            settings = "os", "compiler", "arch", "build_type"
            exports_sources = "CMakeLists.txt", "main.cpp"
            generators = "CMakeDeps", "CMakeToolchain"

            def layout(self):
                cmake_layout(self)

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
    system_name = 'Darwin' if op_system == 'Macos' else 'iOS'
    assert "CMAKE_SYSTEM_NAME: {}".format(system_name) in client.out
    assert "CMAKE_SYSTEM_PROCESSOR: arm64" in client.out
    main_path = "./build/Release/main.app/main" if op_system == "iOS" \
        else "./build/Release/main"
    client.run_command("lipo -info {}".format(main_path))
    assert "Non-fat file" in client.out
    assert "is architecture: arm64" in client.out
    client.run_command(f"vtool -show-build {main_path}")

    if op_system == "Macos":
        assert "platform MACOS"
    elif op_system == "iOS":
        assert "platform IOS"
        assert "minos 12.0"