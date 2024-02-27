import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only OSX")
#@pytest.mark.tool("cmake")
def test_create_universal_binary():
    client = TestClient()

    conanfile = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMake, cmake_layout, CMakeDeps


        class mylibraryRecipe(ConanFile):
            name = "mylibrary"
            version = "1.0"
            package_type = "library"

            # Optional metadata
            license = "<Put the package license here>"
            author = "<Put your name here> <And your email here>"
            url = "<Package recipe repository url here, for issues about the package>"
            description = "<Description of mylibrary package here>"
            topics = ("<Put some tag here>", "<here>", "<and here>")

            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"
            options = {"shared": [True, False], "fPIC": [True, False]}
            default_options = {"shared": False, "fPIC": True}

            # Sources are located in the same place as this recipe, copy them to the recipe
            exports_sources = "CMakeLists.txt", "src/*", "include/*"

            def config_options(self):
                if self.settings.os == "Windows":
                    self.options.rm_safe("fPIC")

            def configure(self):
                if self.options.shared:
                    self.options.rm_safe("fPIC")

            def layout(self):
                cmake_layout(self)

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                tc.generate()

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
                # leaving can_run here to test the real case
                if can_run(self):
                    exe = os.path.join(self.cpp.build.bindir, "example")
                    self.run(exe, env="conanrun")
                    self.run(f"lipo {exe} -info", env="conanrun")
            """)

    client.run("new cmake_lib -d name=mylibrary -d version=1.0")
    client.save({"conanfile.py": conanfile, "test_package/conanfile.py": test_conanfile})

    client.run('create . -s="arch=x86_64-armv8" --build=missing -tf=""')

    assert "libmylibrary.a are: x86_64 arm64" in client.out

    client.run('test test_package mylibrary/1.0 -s="arch=x86_64-armv8" '
               '-c tools.build.cross_building:can_run=True')

    assert "example are: x86_64 arm64" in client.out

