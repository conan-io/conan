import os

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


def test_cache_integrity():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name pkg1 --version 1.0")
    t.run("create . --name pkg2 --version=2.0")
    pref = t.created_package_reference("pkg2/2.0")
    layout = t.get_latest_pkg_layout(pref)
    conaninfo = os.path.join(layout.package(), "conaninfo.txt")
    save(conaninfo, "[settings]")
    t.run("create . --name pkg3 --version=3.0")
    pref = t.created_package_reference("pkg3/3.0")
    layout = t.get_latest_pkg_layout(pref)
    conaninfo = os.path.join(layout.package(), "conaninfo.txt")
    save(conaninfo, "[settings]")

    t.run("cache check-integrity *", assert_error=True)
    assert "pkg1/1.0: Integrity checked: ok" in t.out
    assert "pkg1/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Integrity checked: ok" in t.out
    assert "ERROR: pkg2/2.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Manifest mismatch" in t.out
    assert "ERROR: pkg3/3.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Manifest mismatch" in t.out
    
