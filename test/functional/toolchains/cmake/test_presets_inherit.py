import json
import os
import platform
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


@pytest.mark.tool("cmake", "3.23")
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
