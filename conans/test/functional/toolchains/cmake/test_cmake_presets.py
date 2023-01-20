import platform
import textwrap

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.tool_cmake(version="3.23")
def test_cmake_presets_with_user_presets_file():
    """ Test the integration of the generated one with a user root CMakePresets.json
    """
    c = TestClient()
    # FIXME: DEVELOP 2: c.run("new cmake_exe -d name=foo -d version=1.0")
    c.run("new foo/1.0 --template cmake_exe")
    conanfile = c.load("conanfile.py")
    conanfile = conanfile.replace("tc = CMakeToolchain(self)",
                                  "tc = CMakeToolchain(self)\n"
                                  "        tc.user_presets_path = 'ConanPresets.json'\n"
                                  "        tc.presets_prefix = 'conan'\n")
    c.save({"conanfile.py": conanfile})
    c.run(f"install . ")
    c.run(f"install . -s build_type=Debug")

    cmake_presets = textwrap.dedent("""
        {
        "version": 4,
        "include": ["./ConanPresets.json"],
        "configurePresets": [
            {
                "name": "default",
                "displayName": "multi config",
                "inherits": "conan-default"
            }
        ],
        "buildPresets": [
            {
                "name": "release",
                "configurePreset": "default",
                "configuration": "Release",
                "inherits": "conan-release"
            },
            {
                "name": "debug",
                "configurePreset": "default",
                "configuration": "Debug",
                "inherits": "conan-debug"
            }
        ]
        }""")
    c.save({"CMakePresets.json": cmake_presets})

    if platform.system() != "Windows":
        c.run_command("cmake --preset debug")
        c.run_command("cmake --build --preset debug")
        c.run_command("./build/Debug/foo")
    else:
        c.run_command("cmake --preset default")
        c.run_command("cmake --build --preset debug")
        c.run_command("build\\Debug\\foo")

    assert "Hello World Debug!" in c.out

    if platform.system() != "Windows":
        c.run_command("cmake --preset release")
        c.run_command("cmake --build --preset release")
        c.run_command("./build/Release/foo")
    else:
        c.run_command("cmake --build --preset release")
        c.run_command("build\\Release\\foo")

    assert "Hello World Release!" in c.out
