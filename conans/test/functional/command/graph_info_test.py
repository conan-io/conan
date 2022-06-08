import pytest

from conans.test.utils.tools import TestClient


class TestBasicCliOutput:

    @pytest.mark.tool("cmake")
    def test_info_prev(self):
        client = TestClient()
        client.run("new cmake_lib -d name=hello -d version=1.0")
        client.run("create .")
        prev = client.created_package_revision("hello/1.0")
        client.run("graph info .")
        assert f"prev: {prev}" in client.out
