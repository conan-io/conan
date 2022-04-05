import os
import re

from conans.model.ref import ConanFileReference, PackageReference
from conans.test.utils.tools import TestClient


def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")

    # TODO: check if we can make it work with the local flow

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out

    # # Create + shared works
    # client.run("create . -o hello:shared=True")
    # assert "hello/0.1: Hello World Release!" in client.out


def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=autotools_exe")

    # TODO: check if we can make it work with the local flow

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
