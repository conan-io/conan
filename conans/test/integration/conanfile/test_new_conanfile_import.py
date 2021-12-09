from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_new_import():
    conanfile = GenConanfile(new_import=True)
    client = TestClient()
    client.save({"conanfile.py": conanfile})
    client.run("create . pkg/0.1@")
