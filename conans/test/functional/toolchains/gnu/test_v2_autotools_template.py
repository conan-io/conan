import platform
import re
import os

import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_lib -d name=hello -d version=0.1")

    # Local flow works
    client.run("install .")
    client.run("build .")

    client.run("export-pkg .")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    ref = RecipeReference.loads("hello/0.1")
    pref = client.get_latest_package_reference(ref, package_id)
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))
    assert os.path.exists(os.path.join(package_folder, "lib", "libhello.a"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.save({}, clean_first=True)
    client.run("new autotools_lib -d name=hello -d version=0.1")
    client.run("create . -o hello/*:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out
    if platform.system() == "Darwin":
        client.run_command("otool -l test_package/test_output/build-release/main")
        assert "libhello.0.dylib" in client.out
    else:
        client.run_command("ldd test_package/test_output/build-release/main")
        assert "libhello.so.0" in client.out


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool("autotools")
def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new autotools_exe -d name=greet -d version=0.1")
    # Local flow works
    client.run("install .")
    client.run("build .")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
