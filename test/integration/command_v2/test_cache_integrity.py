import os

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conans.util.files import save


def test_cache_integrity():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name pkg1 --version 1.0")
    t.run("create . --name pkg2 --version=2.0")
    layout = t.created_layout()
    conaninfo = os.path.join(layout.package(), "conaninfo.txt")
    save(conaninfo, "[settings]")
    t.run("create . --name pkg3 --version=3.0")
    layout = t.created_layout()
    conaninfo = os.path.join(layout.package(), "conaninfo.txt")
    save(conaninfo, "[settings]")

    t.run("cache check-integrity *", assert_error=True)
    assert "pkg1/1.0: Integrity checked: ok" in t.out
    assert "pkg1/1.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Integrity checked: ok" in t.out
    assert "ERROR: pkg2/2.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Manifest mismatch" in t.out
    assert "ERROR: pkg3/3.0:da39a3ee5e6b4b0d3255bfef95601890afd80709: Manifest mismatch" in t.out


def test_cache_integrity_export_sources():
    # https://github.com/conan-io/conan/issues/14840
    t = TestClient(default_server_user=True)
    t.save({"conanfile.py": GenConanfile("pkg", "0.1").with_exports_sources("src/*"),
            "src/mysource.cpp": ""})
    t.run("create .")
    t.run("cache check-integrity *")
    assert "pkg/0.1: Integrity checked: ok" in t.out

    # If we download, integrity should be ok
    # (it failed before, because the manifest is not complete)
    t.run("upload * -r=default -c")
    t.run("remove * -c")
    t.run("install --requires=pkg/0.1")
    t.run("cache check-integrity *")
    assert "pkg/0.1: Integrity checked: ok" in t.out
