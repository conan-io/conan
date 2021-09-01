from conans.test.utils.tools import TestClient


def test_cmake_lib_template():
    client = TestClient(path_with_spaces=False)
    client.run("new hello/0.1 --template=cmake_lib")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    assert "hello/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "hello/0.1: Hello World Debug!" in client.out


def test_cmake_exe_template():
    client = TestClient(path_with_spaces=False)
    client.run("new greet/0.1 --template=cmake_exe")
    # Local flow works
    client.run("install . -if=install")
    client.run("build . -if=install")

    # Create works
    client.run("create .")
    assert "greet/0.1: Hello World Release!" in client.out

    client.run("create . -s build_type=Debug")
    assert "greet/0.1: Hello World Debug!" in client.out
