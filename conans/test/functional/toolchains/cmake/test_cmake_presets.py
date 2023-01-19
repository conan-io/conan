import os
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
    conf = "-c tools.cmake.cmake_layout:build_folder_vars=" \
           "'[\"settings.os\", \"settings.build_type\"]'"
    c.run(f"install . {conf}")
    c.run(f"install . {conf} -s build_type=Debug")
    print(c.current_folder)
    assert os.path.exists(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    #os.remove(os.path.join(c.current_folder, "CMakeUserPresets.json"))
    cmake_presets = textwrap.dedent("""
        {
        "version": 4,
        "include": ["./build/windows-debug/generators/CMakePresets.json",
                    "./build/windows-release/generators/CMakePresets.json"],
        "configurePresets": [
            {
                "name": "my-debug",
                "displayName": "'debug' config",
                "inherits": "windows-debug"
            },
            {
                "name": "my-release",
                "displayName": "'release' config",
                "inherits": "windows-release"
            }
        ],
        "buildPresets": [
            {
                "name": "my-debug",
                "configurePreset": "my-debug",
                "configuration": "Debug",
                "inherits": "windows-debug"
            },
            {
                "name": "my-release",
                "configurePreset": "my-release",
                "configuration": "Release",
                "inherits": "windows-release"
            }
        ]
        }""")
    c.save({"CMakePresets.json": cmake_presets})

    #presets_path = os.path.join(c.current_folder, "build", "windows", "generators", "CMakePresets.json")
    #assert os.path.exists(presets_path)

    if platform.system() != "Windows":
        c.run_command("cmake --preset debug")
        c.run_command("cmake --build --preset debug")
        c.run_command("./build/Debug/foo")
    else:
        c.run_command("cmake --preset my-debug")
        print(c.out)
        c.run_command("cmake --build --preset my-debug")
        print(c.out)
        c.run_command("build\\windows-debug\\Debug\\foo")

    assert "Hello World Debug!" in c.out

    if platform.system() != "Windows":
        c.run_command("cmake --preset my-release")
        c.run_command("cmake --build --preset release")
        c.run_command("./build/Release/foo")
    else:
        c.run_command("cmake --preset my-release")
        c.run_command("cmake --build --preset my-release")
        c.run_command("build\\windows-release\\Release\\foo")

    assert "Hello World Release!" in c.out
