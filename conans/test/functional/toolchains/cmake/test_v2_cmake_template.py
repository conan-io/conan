import os
import re

import pytest

from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_cmake_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    # Local flow works
    client.run("build .")

    client.run("export-pkg .")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    ref = RecipeReference.loads("hello/0.1")
    ref = client.cache.get_latest_recipe_reference(ref)
    pref = PkgReference(ref, package_id)
    pref = client.cache.get_latest_package_reference(pref)
    package_folder = client.get_latest_pkg_layout(pref).package()
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.run("create . -o hello/*:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out


@pytest.mark.tool("cmake")
def test_cmake_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_exe -d name=greet -d version=0.1")
    # Local flow works
    client.run("build .")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
