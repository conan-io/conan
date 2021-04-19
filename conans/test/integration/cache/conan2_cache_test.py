from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestCache:
    def test_conan_export(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile().with_exports_sources("*"),
                     "source.txt": "somesource"})
        client.run("export . mypkg/1.0@user/channel")
        client.run("export . mypkg/2.0@user/channel")
