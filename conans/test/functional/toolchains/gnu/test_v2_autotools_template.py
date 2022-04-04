import platform

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=autotools_lib")
    client.run("install . -if=install")
    client.run("build . -if=install")


@pytest.mark.skipif(platform.system() not in ["Linux", "Darwin"], reason="Requires Autotools")
@pytest.mark.tool_autotools()
def test_autotools_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=autotools_exe")
    client.run("install . -if=install")
    client.run("build . -if=install")
