import pytest

from conan.test.utils.tools import GenConanfile, TestClient
from conans.util.files import save


@pytest.mark.parametrize("build_mode", [None, "patch_mode"])
def test_package_id_not_affected_test_requires(build_mode):
    """
    By default, test_requires do not affect the package_id
    """
    c = TestClient()
    if build_mode is not None:
        save(c.cache.new_config_path, "core.package_id:default_build_mode={build_mode}")
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "1.0"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_test_requires("gtest/1.0")})
    c.run("create gtest")
    c.run("create engine")
    c.run("list engine:*")
    assert "engine/1.0" in c.out
    assert "gtest" not in c.out


def test_package_id_not_affected_test_requires_transitive():
    """
    By default, transitive deps of test_requires do not affect the package_id
    """
    c = TestClient()

    c.save({"zlib/conanfile.py": GenConanfile("zlib", "1.0"),
            "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requires("zlib/1.0"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_test_requires("gtest/1.0")})
    c.run("create zlib")
    c.run("create gtest")
    c.run("create engine")
    c.run("list engine:*")
    assert "engine/1.0" in c.out
    assert "gtest" not in c.out
    assert "zlib" not in c.out
