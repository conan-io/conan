import os

import pytest

from conan.test.utils.tools import TestClient


@pytest.mark.tool("cmake")
def test_cmake_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new cmake_lib -d name=hello -d version=0.1")
    # Local flow works
    client.run("build .")

    client.run("export-pkg .")
    package_folder = client.created_layout().package()
    assert os.path.exists(os.path.join(package_folder, "include", "hello.h"))


@pytest.mark.tool("cmake")
def test_cmake_lib_template_create(matrix_client_shared_debug):
    client = matrix_client_shared_debug
    client.run("new cmake_lib -d name=matrix -d version=1.0")
    # Create works
    client.run("create . --build=never")
    assert "matrix/1.0: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug --build=never")
    assert "matrix/1.0: Hello World Debug!" in client.out

    # Create + shared works
    client.run("create . -o hello/*:shared=True --build=never")
    assert "matrix/1.0: Hello World Release!" in client.out


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
