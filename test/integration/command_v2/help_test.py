from conan.test.utils.tools import TestClient


def test_help_command():
    client = TestClient()

    client.run("--help")
    assert "Consumer commands" in client.out

    client.run("search --help")
    assert "Recipe reference to search for." in client.out

    client.run("list --help")
    assert "List existing recipes, revisions, or packages in the cache (by default) or the remotes." in client.out
