import platform
import textwrap

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_with_user_presets_file():
    """ Test the integration of the generated one with a user root CMakePresets.json
    """
    c = TestClient()
    c.run("new cmake_exe -d name=foo -d version=1.0")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile.replace("tc = CMakeToolchain(self)",
                                  "tc = CMakeToolchain(self)\n"
                                  "        tc.user_presets_path = 'ConanPresets.json'\n"
                                  "        tc.presets_prefix = 'conan'\n")
    cmake_presets = textwrap.dedent("""
        {
        "version": 4,
        "include": ["./ConanPresets.json"],
        "configurePresets": [
            {
                "name": "default",
                "displayName": "multi config",
                "inherits": "conan-default"
            },
            {
                "name": "release",
                "displayName": "release single config",
                "inherits": "conan-release"
            },
            {
                "name": "debug",
                "displayName": "debug single config",
                "inherits": "conan-debug"
            }
        ],
        "buildPresets": [
            {
                "name": "multi-release",
                "configurePreset": "default",
                "configuration": "Release",
                "inherits": "conan-release"
            },
            {
                "name": "multi-debug",
                "configurePreset": "default",
                "configuration": "Debug",
                "inherits": "conan-debug"
            },
            {
                "name": "release",
                "configurePreset": "release",
                "configuration": "Release",
                "inherits": "conan-release"
            },
            {
                "name": "debug",
                "configurePreset": "debug",
                "configuration": "Debug",
                "inherits": "conan-debug"
            }
        ]
        }""")
    c.save({"conanfile.py": conanfile,
            "CMakePresets.json": cmake_presets})

    c.run(f"install . ")
    c.run(f"install . -s build_type=Debug")

    if platform.system() != "Windows":
        c.run_command("cmake --preset debug")
        c.run_command("cmake --build --preset debug")
        c.run_command("./build/Debug/foo")
    else:
        c.run_command("cmake --preset default")
        c.run_command("cmake --build --preset multi-debug")
        c.run_command("build\\Debug\\foo")

    assert "Hello World Debug!" in c.out

    if platform.system() != "Windows":
        c.run_command("cmake --preset release")
        c.run_command("cmake --build --preset release")
        c.run_command("./build/Release/foo")
    else:
        c.run_command("cmake --build --preset multi-release")
        c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out


@pytest.mark.tool("cmake", "3.23")
def test_inherit_custom_folders():
    # https://github.com/conan-io/conan/issues/17324
    conanfile = textwrap.dedent("""\
        from conan import ConanFile
        from conan.tools.cmake import CMakeToolchain, CMakeDeps, cmake_layout
        from conan.tools.files import load, save
        import os

        class CompressorRecipe(ConanFile):
            # Binary configuration
            settings = "os", "compiler", "build_type", "arch"

            def layout(self):
                self.folders.build_folder_vars = ["settings.compiler"]
                cmake_layout(self)

            def generate(self):
                deps = CMakeDeps(self)
                deps.generate()
                tc = CMakeToolchain(self)
                tc.user_presets_path = "ConanCMakePresets.json"
                tc.generate()
        """)
    presets = textwrap.dedent("""\
        {
            "version": 4,
            "include": ["ConanCMakePresets.json"],
            "configurePresets": [
                {
                    "name": "gcc",
                    "generator": "Ninja Multi-Config",
                    "inherits": ["conan-gcc"],
                    "binaryDir": "${sourceDir}/build"
                }
            ],
            "buildPresets": [
                {
                    "name": "gcc-release",
                    "configuration": "Release",
                    "configurePreset": "gcc",
                    "inherits": ["conan-gcc-release"]
                },
                {
                    "name": "gcc-debug",
                    "configuration": "Debug",
                    "configurePreset": "gcc",
                    "inherits": ["conan-gcc-debug"]
                }
            ]
        }
        """)
    c = TestClient()
    c.save({"conanfile.py": conanfile,
            "CMakeLists.txt": "",  # Irrelevant, only needed for Conan to generate the presets
            "CMakePresets.json": presets})
    conf = '-s compiler=gcc -s compiler.version=11 -s compiler.libcxx=libstdc++ ' \
           '-c tools.cmake.cmaketoolchain:generator="Ninja Multi-Config"'
    c.run(f"install . --build=missing -s build_type=Release {conf}")
    print(c.out)
    print(c.load("ConanCMakePresets.json"))
    print(c.load("build/gcc/generators/CMakePresets.json"))

    c.run(f"install . --build=missing -s build_type=Debug {conf}")
    print(c.out)
    print(c.load("ConanCMakePresets.json"))
    print(c.load("build/gcc/generators/CMakePresets.json"))
    c.run_command("cmake --list-presets")
    print(c.out)
    assert "gcc" in c.out
    assert "conan-gcc" in c.out
