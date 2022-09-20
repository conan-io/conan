from conan.tools.env.environment import environment_wrap_command
from conans.test.assets.pkg_cmake import pkg_cmake, pkg_cmake_app, pkg_cmake_test
from conans.test.utils.tools import TestClient


def test_shared_cmake_toolchain():
    client = TestClient(default_server_user=True)

    client.save(pkg_cmake("hello", "0.1"))
    client.run("create . -o hello:shared=True")
    client.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.save(pkg_cmake_app("app", "0.1", requires=["chat/0.1"]), clean_first=True)
    client.run("create . -o chat:shared=True -o hello:shared=True")
    client.run("upload * --all -c")
    client.run("remove * -f")

    client = TestClient(servers=client.servers, users=client.users)
    client.run("install app/0.1@ -o chat:shared=True -o hello:shared=True -g VirtualRunEnv")
    command = environment_wrap_command("conanrun", client.current_folder, "app")

    client.run_command(command)
    assert "main: Release!" in client.out
    assert "chat: Release!" in client.out
    assert "hello: Release!" in client.out


def test_shared_cmake_toolchain_test_package():
    client = TestClient()
    files = pkg_cmake("hello", "0.1")
    files.update(pkg_cmake_test("hello"))
    client.save(files)
    client.run("create . -o hello:shared=True")
    assert "hello: Release!" in client.out
