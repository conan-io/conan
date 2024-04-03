from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cps():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create pkg")
    c.run("install --requires=pkg/0.1 -g CPSDeps")
    print(c.out)
