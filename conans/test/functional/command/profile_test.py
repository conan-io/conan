import json
import os
import platform
import subprocess
import textwrap
import pytest

from conans.client.conf.detect import detect_defaults_settings
from conans.test.utils.mocks import RedirectedTestOutput
from conans.test.utils.tools import TestClient, redirect_output
from conans.util.env import environment_update
from conans.util.files import save
from conans.util.runners import check_output_runner
from conan.tools.microsoft.visual import vcvars_command


def test_list_empty():
    client = TestClient()
    client.run("profile list")
    assert "Profiles found in the cache:" in client.out


def test_list():
    client = TestClient()
    profiles = ["default", "profile1", "profile2", "profile3",
                "nested" + os.path.sep + "profile4",
                "nested" + os.path.sep + "two" + os.path.sep + "profile5",
                "nested" + os.path.sep + "profile6"]
    if platform.system() != "Windows":
        profiles.append("symlink_me" + os.path.sep + "profile7")
    for profile in profiles:
        save(os.path.join(client.cache.profiles_path, profile), "")

    if platform.system() != "Windows":
        os.symlink(os.path.join(client.cache.profiles_path, 'symlink_me'),
                   os.path.join(client.cache.profiles_path, 'link'))
        # profile7 will be shown twice because it is symlinked.
        profiles.append("link" + os.path.sep + "profile7")

    # Make sure local folder doesn't interact with profiles
    os.mkdir(os.path.join(client.current_folder, "profile3"))
    client.run("profile list")
    for p in profiles:
        assert p in client.out

    # Test profile list json file
    client.run("profile list --format=json", redirect_stdout="profiles_list.json")
    json_content = client.load("profiles_list.json")
    json_obj = json.loads(json_content)
    assert type(json_obj) == list
    assert set(profiles) == set(json_obj)


def test_show():
    client = TestClient()
    profile1 = textwrap.dedent("""
        [settings]
        os=Windows
        [options]
        MyOption=32
        [conf]
        tools.build:jobs=20
        """)

    client.save({"profile1": profile1})
    client.run("profile show -pr=profile1")
    assert "[settings]\nos=Windows" in client.out
    assert "MyOption=32" in client.out
    assert "tools.build:jobs=20" in client.out

    client.run("profile show -pr=profile1 -pr:b=profile1 -f=json", redirect_stdout="profile1.json")
    profile = json.loads(client.load("profile1.json"))
    assert profile == {'host': {'settings': {'os': 'Windows'}, 'package_settings': {},
                                'options': {'MyOption': '32'}, 'tool_requires': {},
                                'conf': {'tools.build:jobs': 20}, 'build_env': ''},
                       'build': {'settings': {'os': 'Windows'}, 'package_settings': {},
                                 'options': {'MyOption': '32'}, 'tool_requires': {},
                                 'conf': {'tools.build:jobs': 20}, 'build_env': ''}}


def test_missing_subarguments():
    client = TestClient()
    client.run("profile", assert_error=True)
    assert "ERROR: Exiting with code: 2" in client.out


def test_detect_default_compilers():
    platform_default_compilers = {
        "Linux": "gcc",
        "Darwin": "apple-clang",
        "Windows": "msvc"
    }

    result = detect_defaults_settings()
    # result is a list of tuples (name, value) so converting it to dict
    result = dict(result)
    platform_compiler = platform_default_compilers.get(platform.system(), None)
    if platform_compiler is not None:
        assert result.get("compiler", None) == platform_compiler


@pytest.mark.tool("gcc")
@pytest.mark.skipif(platform.system() != "Darwin", reason="only OSX test")
def test_detect_default_in_mac_os_using_gcc_as_default():
    """
    Test if gcc in Mac OS X is using apple-clang as frontend
    """
    # See: https://github.com/conan-io/conan/issues/2231
    output = check_output_runner("gcc --version", stderr=subprocess.STDOUT)

    if "clang" not in output:
        # Not test scenario gcc should display clang in output
        # see: https://stackoverflow.com/questions/19535422/os-x-10-9-gcc-links-to-clang
        raise Exception("Apple gcc doesn't point to clang with gcc frontend anymore!")

    output = RedirectedTestOutput()  # Initialize each command
    with redirect_output(output):
        with environment_update({"CC": "gcc"}):
            result = detect_defaults_settings()
    # result is a list of tuples (name, value) so converting it to dict
    result = dict(result)
    # No compiler should be detected
    assert result.get("compiler", None) is None
    assert "gcc detected as a frontend using apple-clang" in output


def test_profile_new():
    c = TestClient()
    c.run("profile detect --name=./MyProfile2")
    assert "os=" in c.out
    assert "compiler.runtime_type" not in c.out  # Even in Windows

    c.run("profile detect --name=./MyProfile2", assert_error=True)
    assert "MyProfile2' already exists" in c.out

    c.run("profile detect --name=./MyProfile2 --force")  # will not raise error

    c.run("profile detect --name=./MyProfile3 -o *:my_custom_option=42 -s compiler.cppstd=gnu98")
    assert "*:my_custom_option=42" in c.out
    assert "compiler.cppstd=gnu98" in c.out  # Override from default detected one


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows and msvc")
def test_profile_new_msvc_vcvars():
    c = TestClient()

    # extract location of cl.exe from vcvars
    vcvars = vcvars_command(version="15", architecture="x64")
    ret = c.run_command(f"{vcvars} && where cl.exe")
    assert ret == 0
    cl_executable = c.out.splitlines()[-1]
    assert os.path.isfile(cl_executable)
    cl_location = os.path.dirname(cl_executable)

    # Try different variations, including full path and full path with quotes
    for var in ["cl", "cl.exe", cl_executable, f'"{cl_executable}"']:
        output = RedirectedTestOutput()
        with redirect_output(output):
            with environment_update({"CC": var, "PATH": cl_location}):
                c.run("profile detect --name=./cl-profile --force")

        profile = c.load("cl-profile")
        assert "compiler=msvc" in profile
        assert "compiler.version=191" in profile
