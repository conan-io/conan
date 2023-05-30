from conans.test.utils.tools import TestClient


def test_version_json():
    t = TestClient()
    t.run("version --format=json")
    assert ['{', '    "version": "2.0.4"', '}'] == t.out.splitlines()


def test_version_text():
    t = TestClient()
    t.run("version --format=text")
    assert ['Conan version 2.0.4'] == t.out.splitlines()


def test_version_raw():
    t = TestClient()
    t.run("version")
    assert ['Conan version 2.0.4'] == t.out.splitlines()
