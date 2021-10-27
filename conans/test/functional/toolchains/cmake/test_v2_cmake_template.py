import os
import re

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient


def test_cmake_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    client.run("export-pkg . hello/0.1@ -if=install")
    package_id = re.search(r"Packaging to (\S+)", str(client.out)).group(1)
    pref = PackageReference(ConanFileReference.loads("hello/0.1"), package_id)
    package_folder = client.cache.package_layout(pref.ref).package(pref)
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # Create + shared works
    client.run("create . -o hello:shared=True")
    assert "hello/0.1: Hello World Release!" in client.out


def test_cmake_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=cmake_exe")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
