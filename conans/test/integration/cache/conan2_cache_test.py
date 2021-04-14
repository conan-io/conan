from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestCache:
    def test_conan_export(self):
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("export .")
