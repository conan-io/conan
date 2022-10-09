from conans.test.utils.tools import TestClient


def test_profile_path():
    c = TestClient()
    c.run("profile path default")
    assert "default" in c.out
