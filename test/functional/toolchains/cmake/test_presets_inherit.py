import json
import os
import platform
import shutil
import textwrap
from shutil import rmtree

import pytest

from conan.test.utils.tools import TestClient

# Shared CMakePresets.json for tests that use user_presets_path + ConanPresets.json
_CMAKE_PRESETS_FILE = textwrap.dedent("""
    {
      "version": 4,
      "include": ["./ConanPresets.json"],
      "configurePresets": [
        {"name": "default", "displayName": "multi config", "inherits": "conan-default"},
        {"name": "release", "displayName": "release single config", "inherits": "conan-release"},
        {"name": "debug", "displayName": "debug single config", "inherits": "conan-debug"}
      ],
      "buildPresets": [
        {"name": "multi-release", "configurePreset": "default", "configuration": "Release", "inherits": "conan-release"},
        {"name": "multi-debug", "configurePreset": "default", "configuration": "Debug", "inherits": "conan-debug"},
        {"name": "release", "configurePreset": "release", "configuration": "Release", "inherits": "conan-release"},
        {"name": "debug", "configurePreset": "debug", "configuration": "Debug", "inherits": "conan-debug"}
      ]
    }
""")


def _client_with_user_presets():
    """TestClient with cmake_exe, user_presets_path and standard CMakePresets.json."""
    c = TestClient()
    c.run("new cmake_exe -d name=foo -d version=1.0")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile.replace(
        "tc = CMakeToolchain(self)",
        "tc = CMakeToolchain(self)\n        tc.user_presets_path = 'ConanPresets.json'",
    )
    c.save({"conanfile.py": conanfile, "CMakePresets.json": _CMAKE_PRESETS_FILE})
    return c


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
    c.save({"conanfile.py": conanfile,
            "CMakePresets.json": _CMAKE_PRESETS_FILE})

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


class TestCMakeLayoutBuildFolder:
    @pytest.mark.tool("cmake", "3.23")
    def test_inherit_custom_folders(self):
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

    def test_build_folder_vars_empty(self):
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile
            from conan.tools.cmake import cmake_layout

            class Conan(ConanFile):
                name = "pkg"
                version = "0.1"
                settings = "os", "build_type"
                generators = "CMakeToolchain"

                def layout(self):
                    self.folders.build_folder_vars = []
                    cmake_layout(self)
            """)
        client.save({"conanfile.py": conanfile})
        client.run("install . -s os=Windows -s build_type=Debug")
        print(client.out)
        presets = client.load("build/generators/CMakePresets.json")
        assert "conan-debug" in presets

    def test_build_folder_vars_combinations(self):
        c = TestClient()
        c.run("new cmake_exe -d name=hello -d version=0.1")
        settings = ("-s compiler=gcc -s compiler.version=9 "
                    "-s compiler.libcxx=libstdc++ -s compiler.cppstd=17")

        # NINJA
        generator = "-c tools.cmake.cmaketoolchain:generator=Ninja"

        # NINJA + build_folder_vars = cppstd
        conf = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.compiler.cppstd"]\''
        c.run(f"install . {settings} {conf} {generator}")
        # The folder is now "17/Release" (a nested subfolder, automatic for Release/Debug)
        presets = json.loads(c.load("build/17/Release/generators/CMakePresets.json"))
        assert presets["configurePresets"][0]["name"] == "conan-17-release"
        assert presets["buildPresets"][0]["name"] == "conan-17-release"

        # NINJA + build_folder_vars = cppstd, build_type
        shutil.rmtree(os.path.join(c.current_folder, "build"))
        conf = ('-c tools.cmake.cmake_layout:build_folder_vars='
                '\'["settings.compiler.cppstd", "settings.build_type"]\'')
        c.run(f"install . {settings} {conf} {generator}")
        # The folder is now "17-release"
        presets = json.loads(c.load("build/17-release/generators/CMakePresets.json"))
        assert presets["configurePresets"][0]["name"] == "conan-17-release"
        assert presets["buildPresets"][0]["name"] == "conan-17-release"

        # NINJA Multi-Config
        generator = '-c tools.cmake.cmaketoolchain:generator="Ninja Multi-Config"'

        # NINJA Multi-Config + build_folder_vars = cppstd
        shutil.rmtree(os.path.join(c.current_folder, "build"))
        conf = '-c tools.cmake.cmake_layout:build_folder_vars=\'["settings.compiler.cppstd"]\''
        c.run(f"install . {settings} {conf} {generator}")
        # The folder is now "17" (for both configs it is the same)
        presets = json.loads(c.load("build/17/generators/CMakePresets.json"))
        assert presets["configurePresets"][0]["name"] == "conan-17"
        assert presets["buildPresets"][0]["name"] == "conan-17-release"

        # NINJA Multi-Config+ build_folder_vars = cppstd, build_type
        shutil.rmtree(os.path.join(c.current_folder, "build"))
        conf = ('-c tools.cmake.cmake_layout:build_folder_vars='
                '\'["settings.compiler.cppstd", "settings.build_type"]\'')
        c.run(f"install . {settings} {conf} {generator}")
        # The folder is now "17-release", even if it is multi-config, it will have a dedicated folder
        presets = json.loads(c.load("build/17-release/generators/CMakePresets.json"))
        assert presets["configurePresets"][0]["name"] == "conan-17-release"
        assert presets["buildPresets"][0]["name"] == "conan-17-release"


def test_cmake_presets_build_preset_stub_needs_configure_preset():
    """Reproduce issue #19180: buildPresets stubs in ConanPresets.json must include
    'configurePreset' field for cmake --list-presets to succeed (single-config generators).
    """
    c = _client_with_user_presets()
    c.run("install .")

    conan_presets = json.loads(c.load("ConanPresets.json"))
    for stub in conan_presets.get("buildPresets", []):
        assert "configurePreset" in stub

    c.run_command("cmake --list-presets")
    assert "Invalid preset" not in c.out, f"cmake --list-presets failed: {c.out}"


@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_stubs_restored_after_build_folder_deleted():
    """Reproduce issue #19173: after deleting build/ and reinstalling one config,
    ConanPresets.json must still contain stubs for presets inherited by user (e.g. conan-release)
    so cmake --list-presets does not fail.
    """
    c = _client_with_user_presets()
    c.run("install . -s build_type=Debug")
    c.run("install . -s build_type=Release")

    rmtree(os.path.join(c.current_folder, "build"))
    c.run("install . -s build_type=Debug")

    conan_presets = json.loads(c.load("ConanPresets.json"))
    stub_names = {s["name"] for s in conan_presets.get("configurePresets", [])}
    assert "conan-release" in stub_names

    c.run_command("cmake --list-presets")
    assert "Invalid preset" not in c.out, f"cmake --list-presets failed: {c.out}"
