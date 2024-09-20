import os
import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from conans.util.files import rmdir


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool("cmake", "3.23")
def test_create_universal_binary():
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        class mylibraryRecipe(ConanFile):
            package_type = "library"
            generators = "CMakeToolchain"
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def layout(self):
                cmake_layout(self)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()
                self.run("lipo -info libmylibrary.a")

            def package(self):
                cmake = CMake(self)
                cmake.install()

            def package_info(self):
                self.cpp_info.libs = ["mylibrary"]
    """)

    test_conanfile = textwrap.dedent("""
        import os
        from conan import ConanFile
        from conan.tools.cmake import CMake, cmake_layout
        from conan.tools.build import can_run

        class mylibraryTestConan(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            generators = "CMakeDeps", "CMakeToolchain"

            def requirements(self):
                self.requires(self.tested_reference_str)

            def build(self):
                cmake = CMake(self)
                cmake.configure()
                cmake.build()

            def layout(self):
                cmake_layout(self)

            def test(self):
                exe = os.path.join(self.cpp.build.bindir, "example")
                self.run(f"lipo {exe} -info", env="conanrun")
            """)

    client.run("new cmake_lib -d name=mylibrary -d version=1.0")
    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile})

    client.run('create . --name=mylibrary --version=1.0 '
               '-s="arch=armv8|armv8.3|x86_64" --build=missing -tf=""')

    assert "libmylibrary.a are: x86_64 arm64 arm64e" in client.out

    client.run('test test_package mylibrary/1.0 -s="arch=armv8|armv8.3|x86_64"')

    assert "example are: x86_64 arm64 arm64e" in client.out

    client.run('new cmake_exe -d name=foo -d version=1.0 -d requires=mylibrary/1.0 --force')

    client.run('install . -s="arch=armv8|armv8.3|x86_64"')

    client.run_command("cmake --preset conan-release")
    client.run_command("cmake --build --preset conan-release")
    client.run_command("lipo -info ./build/Release/foo")

    assert "foo are: x86_64 arm64 arm64e" in client.out

    rmdir(os.path.join(client.current_folder, "build"))

    client.run('install . -s="arch=armv8|armv8.3|x86_64" '
               '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.arch"]\'')

    client.run_command("cmake --preset \"conan-armv8|armv8.3|x86_64-release\" ")
    client.run_command("cmake --build --preset \"conan-armv8|armv8.3|x86_64-release\" ")
    client.run_command("lipo -info './build/armv8|armv8.3|x86_64/Release/foo'")

    assert "foo are: x86_64 arm64 arm64e" in client.out


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
@pytest.mark.tool("cmake", "3.23")
def test_create_universal_binary_ninja():
    client = TestClient()

    client.run("new cmake_lib -d name=mylibrary -d version=1.0")

    client.run('export .')

    conanfile = textwrap.dedent("""
        [requires]
        mylibrary/1.0
        [generators]
        CMakeToolchain
        CMakeDeps
        VirtualBuildEnv
        VirtualRunEnv
        """)

    cmake = textwrap.dedent("""
        cmake_minimum_required(VERSION 3.23)
        project(ninjatest CXX)

        find_package(mylibrary CONFIG REQUIRED)
        """)

    client.save({"conanfile.txt": conanfile,
                 "CMakeLists.txt": cmake},
                 clean_first=True)

    client.run('install . -s=arch="armv8|x86_64" --build=missing -of=build')

    with client.chdir("build"):
        client.run_command("cmake .. -GNinja "
                           "-DCMAKE_TOOLCHAIN_FILE=conan_toolchain.cmake "
                           "-DCMAKE_POLICY_DEFAULT_CMP0091=NEW "
                           "-DCMAKE_BUILD_TYPE=Release")

    assert "expected newline, got '|'" not in client.out
    assert "Build files have been written to:" in client.out
    # test that there are no files with the "|" character in the build folder
    assert not any("|" in f for f in os.listdir(os.path.join(client.current_folder, "build")))
