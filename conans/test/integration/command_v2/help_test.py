from conans.test.utils.tools import TestClient


def test_help_command():
    client = TestClient()

    client.run("--help")
    assert "Consumer commands" in client.out

    client.run("search --help")
    assert "Searches for package recipes in a remote or remotes" in client.out

    client.run("list recipes --help")
    assert "Search query to find package recipe reference" in client.out
