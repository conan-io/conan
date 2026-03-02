import json
import os
import platform
import textwrap
from shutil import rmtree

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


#@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_build_preset_stub_needs_configure_preset():
    """Reproduce issue #19180: buildPresets stubs in ConanPresets.json must include
    'configurePreset' field for cmake --list-presets to succeed (single-config generators).
    """
    c = TestClient()
    c.run("new cmake_exe -d name=foo -d version=1.0")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile.replace(
        "tc = CMakeToolchain(self)",
        "tc = CMakeToolchain(self)\n        tc.user_presets_path = 'ConanPresets.json'",
    )
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
        }
    """)
    c.save({"conanfile.py": conanfile, "CMakePresets.json": cmake_presets})

    # Single install (e.g. Release) -> Conan generates only one config; stubs for the other
    c.run("install . --build=missing")

    conan_presets_path = os.path.join(c.current_folder, "ConanPresets.json")
    assert os.path.exists(conan_presets_path)
    conan_presets = json.loads(c.load("ConanPresets.json"))

    # buildPresets stubs must have "configurePreset" so cmake --list-presets does not fail
    for stub in conan_presets.get("buildPresets", []):
        assert "configurePreset" in stub

    c.run_command("cmake --list-presets")
    assert "Invalid preset" not in c.out, f"cmake --list-presets failed: {c.out}"


#@pytest.mark.tool("cmake", "3.23")
def test_cmake_presets_stubs_restored_after_build_folder_deleted():
    """Reproduce issue #19173: after deleting build/ and reinstalling one config,
    ConanPresets.json must still contain stubs for presets inherited by user (e.g. conan-release)
    so cmake --list-presets does not fail.
    """
    c = TestClient()
    c.run("new cmake_exe -d name=foo -d version=1.0")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile.replace(
        "tc = CMakeToolchain(self)",
        "tc = CMakeToolchain(self)\n        tc.user_presets_path = 'ConanPresets.json'",
    )
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
        }
    """)
    c.save({"conanfile.py": conanfile, "CMakePresets.json": cmake_presets})

    c.run("install . -s build_type=Debug")
    c.run("install . -s build_type=Release")

    # Delete build folder and reinstall only one config (as in issue #19173)
    build_dir = os.path.join(c.current_folder, "build")
    rmtree(build_dir)
    c.run("install . -s build_type=Debug")

    conan_presets_path = os.path.join(c.current_folder, "ConanPresets.json")
    assert os.path.exists(conan_presets_path)
    conan_presets = json.loads(c.load("ConanPresets.json"))

    # Stubs for inherited presets (e.g. conan-release) must be present so user presets stay valid
    configure_stubs = conan_presets.get("configurePresets", [])
    stub_names = {s["name"] for s in configure_stubs}
    assert "conan-release" in stub_names

    c.run_command("cmake --list-presets")
    assert "Invalid preset" not in c.out, f"cmake --list-presets failed: {c.out}"
