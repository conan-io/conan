from conans.test.assets.pkg_cmake import pkg_cmake
from conans.test.utils.tools import TestClient


def test_shared_cmake_toolchain():
    client = TestClient(default_server_user=True)
    client.save(pkg_cmake("hello", "0.1"))
    client.run("create . -o hello:shared=True")
    client.save(pkg_cmake("chat", "0.1", requires=["hello/0.1"]))
    client.run("create . -o chat:shared=True -o hello:shared=True")

    client.save(pkg_cmake("app", "0.1", requires=["chat/0.1"]))
    client.run("create . -o chat:shared=True -o hello:shared=True")

    client.run("install app/0.1@ -g VirtualEnv")
    client.run_command("app")



