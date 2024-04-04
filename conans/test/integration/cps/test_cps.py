import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cps():
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create pkg")

    c.run("install --requires=pkg/0.1 -g CPSDeps")
    pkg = json.loads(c.load("pkg.cps"))
    print(json.dumps(pkg, indent=2))
    assert pkg["Name"] == "pkg"
    assert pkg["Version"] == "0.1"
    assert pkg["Configurations"] == ["release"]
    assert pkg["Name"] == "pkg"
    assert pkg["Default-Components"] == ["pkg"]
    pkg_comp = pkg["Components"]["pkg"]
