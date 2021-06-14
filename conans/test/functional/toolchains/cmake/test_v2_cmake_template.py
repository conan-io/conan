from conans.test.utils.tools import TestClient


def test_v2_cmake_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=v2_cmake")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    assert "Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "Hello World Debug!" in client.out
