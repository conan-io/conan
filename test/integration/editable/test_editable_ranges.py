from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_editable_ranges():
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep"),
            "dep2/conanfile.py": GenConanfile("dep", "0.2"),
            "other/conanfile.py": GenConanfile("other", "23.0"),  # shouldn't be resolved!
            "app/conanfile.py": GenConanfile("app", "0.1").with_requires("dep/[>=0.1]")})
    c.run("editable add other")  # This shouldn't be used
    c.run("editable add dep --version=0.1")  # this should be used
    c.run("editable add dep --version=2.0 --user=myuser --channel=mychannel")  # This shouldn't be used
    c.run("install app")
    c.assert_listed_require({"dep/0.1": "Editable"})
    assert "dep/[>=0.1]: dep/0.1" in c.out

    # new version, uses new one
    c.run("editable add dep2")
    c.run("install app")
    c.assert_listed_require({"dep/0.2": "Editable"})
    assert "dep/[>=0.1]: dep/0.2" in c.out
    assert "dep/0.1" not in c.out

    # If a newer one is in cache, it resolves to cache
    c.run("create dep --version=0.3")
    c.run("install app")
    c.assert_listed_require({"dep/0.3": "Cache"})
    assert "dep/[>=0.1]: dep/0.3" in c.out
    assert "dep/0.1" not in c.out
