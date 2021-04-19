from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestCache:
    def test_conan_export(self):
        client = TestClient()
        client.cache_folder = "/Users/carlos/Documents/developer/conan-develop/sandbox/cache2.0"
        client.run("new mypkg/1.0@user/channel -s")
        client.run("export .")
        client.run("new mypkg/2.0@user/channel")
        client.run("export .")
        print("ddd")
