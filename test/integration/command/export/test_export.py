import textwrap

from conan.test.utils.tools import TestClient


def test_basic():
    client = TestClient()
    conanfile = textwrap.dedent("""
        from conan import ConanFile
        class TestConan(ConanFile):
            name = "hello"
            version = "1.2"
            user = "myuser"
            channel = "mychannel"
        """)
    client.save({"conanfile.py": conanfile})
    client.run("export .")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("list *")
    assert "hello/1.2@myuser/mychannel" in client.out
    client.run("create .")
    assert "hello/1.2@myuser/mychannel" in client.out
    assert "hello/1.2:" not in client.out
