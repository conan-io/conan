import os
import platform
import re

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_msbuild_lib_template():
    client = TestClient()
    client.run("new msbuild_lib -d name=hello -d version=0.1")
    # Local flow works
    client.run("install .")
    client.run("build .")

    assert os.path.isfile(os.path.join(client.current_folder, "x64", "Release", "hello.lib"))
    client.run("export-pkg .")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    ref = RecipeReference.loads("hello/0.1")
    pref = client.get_latest_package_reference(ref, package_id)
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))
    assert os.path.exists(os.path.join(package_folder, "lib", "hello.lib"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out
    assert "hello/0.1: _MSC_VER191" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # FIXME: Create + shared DOESNT work fine, the proj is hardcoded to static
    # client.run("create . -o hello:shared=True")
    # assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
@pytest.mark.tool("visual_studio", "17")
def test_msbuild_lib_2022():
    # The template .vcxproj are MSBuildTools=15, so it won't work with older versions
    # 2022 Must have installed the v141 toolset too
    client = TestClient(path_with_spaces=False)
    client.run("new msbuild_lib -d name=hello -d version=0.1")

    # Create works
    client.run("create . -s compiler.version=191 -c tools.microsoft.msbuild:vs_version=17")
    assert "hello/0.1: Hello World Release!" in client.out
    # This is the default compiler.version=191 in conftest
    assert "Visual Studio 2022" in client.out
    assert "hello/0.1: _MSC_VER191" in client.out

    # Create works
    client.run("create . -s compiler.version=193")
    assert "hello/0.1: Hello World Release!" in client.out
    # This is the default compiler.version=191 in conftest
    assert "Visual Studio 2022" in client.out
    assert "hello/0.1: _MSC_VER193" in client.out


@pytest.mark.skipif(platform.system() != "Windows", reason="Requires Windows")
def test_msbuild_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new msbuild_exe -d name=greet -d version=0.1")
    # Local flow works
    client.run("install .")
    client.run("build .")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
