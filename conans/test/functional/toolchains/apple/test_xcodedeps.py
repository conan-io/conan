import platform

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Darwin", reason="Only for MacOS")
def test_basic():
    client = TestClient()
    client.run("new hello/0.1 -m=cmake_lib")
    client.run("create .")
    # client.run("new goodbye/0.1 -m=cmake_lib")
    # client.run("create .")
    client.save({"conanfile.txt": "[requires]\nhello/0.1"}, clean_first=True)  # \ngoodbye/0.1
    client.run("install . -g XCodeDeps --build=missing -s build_type=Release")
    client.run("install . -g XCodeDeps --build=missing -s build_type=Debug")
