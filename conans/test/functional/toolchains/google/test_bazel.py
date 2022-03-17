from conans.test.utils.tools import TestClient


def test_basic_exe():
    client = TestClient()
    client.run("new myapp/1.0 --template bazel_exe")
    client.run("create .")
