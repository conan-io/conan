import platform

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.skipif(platform.system() != "Linux", reason="SCons functional tests"
                                                         "only for Linux")
@pytest.mark.tool("scons")
def test_sconsdeps():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    client.run("create . -tf=None")
    client.run("install hello/0.1@ -g SconsDeps")
