import platform

import pytest

from conans.test.utils.tools import TestClient


@pytest.fixture(scope="session")
def client():
    return TestClient()


@pytest.mark.skipif(platform.system() != "Windows", reason="Tests Windows Subsystems")
class TestSubsystemsBuild:

    @pytest.mark.tool_msys2
    def test_msys2_available(self, client):
        client.run_command('uname')
        assert "MSYS" in client.out

    def test_msys2_not_available(self, client):
        client.run_command('uname', assert_error=True)
        assert "command not found" in client.out

    @pytest.mark.tool_cygwin
    def test_cygwin_available(self, client):
        client.run_command('uname')
        assert "CYGWIN" in client.out

    def test_cygwin_not_available(self, client):
        client.run_command('uname', assert_error=True)
        assert "command not found" in client.out
