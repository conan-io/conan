import platform

import pytest


from conans.test.utils.tools import TestClient


# TODO: add versions for all platforms
@pytest.mark.skipif(platform.system() != "Windows", reason="Only versions for Windows at the moment")
class TestToolsCustomVersions:

    @pytest.mark.tool_cmake(version="3.16")
    def test_custom_cmake_3_16(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.16" in client.out

    @pytest.mark.tool_cmake(version="3.17")
    def test_custom_cmake_3_17(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.17" in client.out

    @pytest.mark.tool_msys2
    @pytest.mark.tool_cmake(version="3.16")
    def test_custom_cmake_msys2(self):
        client = TestClient()
        client.run_command('cmake --version')
        assert "cmake version 3.16" in client.out
