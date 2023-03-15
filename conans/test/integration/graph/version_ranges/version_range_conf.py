from conans.test.assets.genconanfile import GenConanfile
from utils.tools import TestClient
import textwrap


def test_version_range_conf_nonexplicit_expression():
    tc = TestClient()

    base = textwrap.dedent("""
    from conan import ConanFile

    class Base(ConanFile):
        name = "base"
    """)

    tc.save({"base/conanfile.py": base})
    tc.run("create base/conanfile.py --version=1.5.1")
    tc.run("create base/conanfile.py --version=2.5.0-pre")

    tc.save({"v1/conanfile.py": GenConanfile("pkg", "1.0").with_requires("base/[>1 <2]"),
             "v2/conanfile.py": GenConanfile("pkg", "2.0").with_requires("base/[>2 <3]")})

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=False"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1 <2]: base/1.5.1" in tc.out
    tc.run("create v2/conanfile.py", assert_error=True)
    assert "Package 'base/[>2 <3]' not resolved" in tc.out

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=True"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1 <2]: base/1.5.1" in tc.out
    tc.run("create v2/conanfile.py")
    assert "base/[>2 <3]: base/2.5.0-pre" in tc.out

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=None"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1 <2]: base/1.5.1" in tc.out

    tc.run("create v2/conanfile.py", assert_error=True)
    assert "Package 'base/[>2 <3]' not resolved" in tc.out


def test_version_range_conf_explicit_expression():
    tc = TestClient()

    base = textwrap.dedent("""
    from conan import ConanFile

    class Base(ConanFile):
        name = "base"
    """)

    tc.save({"base/conanfile.py": base})
    tc.run("create base/conanfile.py --version=1.5.1")
    tc.run("create base/conanfile.py --version=2.5.0-pre")

    tc.save({"v1/conanfile.py": GenConanfile("pkg", "1.0").with_requires("base/[>1- <2]"),
             "v2/conanfile.py": GenConanfile("pkg", "2.0").with_requires("base/[>2- <3]")})

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=False"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1- <2]: base/1.5.1" in tc.out
    tc.run("create v2/conanfile.py", assert_error=True)
    assert "Package 'base/[>2- <3]' not resolved" in tc.out

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=True"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1- <2]: base/1.5.1" in tc.out
    tc.run("create v2/conanfile.py")
    assert "base/[>2- <3]: base/2.5.0-pre" in tc.out

    tc.save({"global.conf": "core.version_ranges:resolve_prereleases=None"}, path=tc.cache.cache_folder)
    tc.run("create v1/conanfile.py")
    assert "base/[>1- <2]: base/1.5.1" in tc.out
    tc.run("create v2/conanfile.py")
    assert "base/[>2- <3]: base/2.5.0-pre" in tc.out
