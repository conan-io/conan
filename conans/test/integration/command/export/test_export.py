import textwrap

from conans.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conans import ConanFile
        class TestConan(ConanFile):
            name = "hello"
            version = "1.2"
            default_user = "myuser"
            default_channel = "mychannel"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export .")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("search *")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("create .")
    assert "hello/1.2@myuser/mychannel" in client.out
    assert "hello/1.2:" not in client.out
