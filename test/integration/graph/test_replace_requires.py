import json

import pytest

from conans.model.recipe_ref import RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


@pytest.mark.parametrize("require, pattern, alternative, pkg", [
    # PATTERN VERSIONS
    # override all dependencies to "dep" to a specific version,user and channel)
    # TODO: This is a version override, is this really wanted?
    ("dep/1.3", "dep/*", "dep/1.1", "dep/1.1"),
    ("dep/[>=1.0 <2]", "dep/*", "dep/1.1", "dep/1.1"),
    # override all dependencies to "dep" to the same version with other user, remove channel)
    ("dep/1.3", "dep/*", "dep/*@system", "dep/1.3@system"),
    ("dep/[>=1.0 <2]", "dep/*", "dep/*@system", "dep/1.1@system"),
    # override all dependencies to "dep" to the same version with other user, same channel)
    ("dep/1.3@comp/stable", "dep/*@*/*", "dep/*@system/*", "dep/1.3@system/stable"),
    ("dep/[>=1.0 <2]@comp/stable", "dep/*@*/*", "dep/*@system/*", "dep/1.1@system/stable"),
    # EXACT VERSIONS
    # replace exact dependency version for one in the system
    ("dep/1.1", "dep/1.1", "dep/1.1@system", "dep/1.1@system"),
    ("dep/[>=1.0 <2]", "dep/1.1", "dep/1.1@system", "dep/1.1@system"),
    ("dep/[>=1.0 <2]@comp", "dep/1.1@*", "dep/1.1@*/stable", "dep/1.1@comp/stable"),
    ("dep/1.1@comp", "dep/1.1@*", "dep/1.1@*/stable", "dep/1.1@comp/stable"),
    # PACKAGE ALTERNATIVES (zlib->zlibng)
    ("dep/1.0", "dep/*", "depng/*", "depng/1.0"),
    ("dep/[>=1.0 <2]", "dep/*", "depng/*", "depng/1.1"),
    ("dep/[>=1.0 <2]", "dep/1.1", "depng/1.2", "depng/1.2"),
    # NON MATCHING
    ("dep/1.3", "dep/1.1", "dep/1.1@system", "dep/1.3"),
    ("dep/1.3", "dep/*@comp", "dep/*@system", "dep/1.3"),
    ("dep/[>=1.0 <2]", "dep/2.1", "dep/2.1@system", "dep/1.1"),
    # PATTERN - PATTERN REPLACE
    ("dep/[>=1.3 <2]", "dep/*", "dep/[>=1.0 <1.9]", "dep/1.1"),
])
@pytest.mark.parametrize("tool_require", [False, True])
class TestReplaceRequires:
    def test_alternative(self, tool_require, require, pattern, alternative, pkg):
        c = TestClient(light=True)
        conanfile = GenConanfile().with_tool_requires(require) if tool_require else \
            GenConanfile().with_requires(require)
        profile_tag = "replace_requires" if not tool_require else "replace_tool_requires"
        c.save({"dep/conanfile.py": GenConanfile(),
                "pkg/conanfile.py": conanfile,
                "profile": f"[{profile_tag}]\n{pattern}: {alternative}"})
        ref = RecipeReference.loads(pkg)
        user = f"--user={ref.user}" if ref.user else ""
        channel = f"--channel={ref.channel}" if ref.channel else ""
        c.run(f"create dep --name={ref.name} --version={ref.version} {user} {channel}")
        rrev = c.exported_recipe_revision()
        c.run("profile show -pr=profile")
        assert profile_tag in c.out
        c.run("install pkg -pr=profile")
        assert profile_tag in c.out
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

        # Check lockfile
        c.run("lock create pkg -pr=profile")
        lock = c.load("pkg/conan.lock")
        assert f"{pkg}#{rrev}" in lock

        # c.run("create dep2 --version=1.2")
        # with lockfile
        c.run("install pkg -pr=profile")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

    def test_diamond(self, tool_require, require, pattern, alternative, pkg):
        c = TestClient(light=True)
        conanfile = GenConanfile().with_tool_requires(require) if tool_require else \
            GenConanfile().with_requires(require)
        profile_tag = "replace_requires" if not tool_require else "replace_tool_requires"

        c.save({"dep/conanfile.py": GenConanfile(),
                "libb/conanfile.py": conanfile,
                "libc/conanfile.py": conanfile,
                "app/conanfile.py": GenConanfile().with_requires("libb/0.1", "libc/0.1"),
                "profile": f"[{profile_tag}]\n{pattern}: {alternative}"})
        ref = RecipeReference.loads(pkg)
        user = f"--user={ref.user}" if ref.user else ""
        channel = f"--channel={ref.channel}" if ref.channel else ""
        c.run(f"create dep --name={ref.name} --version={ref.version} {user} {channel}")
        rrev = c.exported_recipe_revision()

        c.run("export libb --name=libb --version=0.1")
        c.run("export libc --name=libc --version=0.1")

        c.run("install app -pr=profile", assert_error=True)
        assert "ERROR: Missing binary: libb/0.1" in c.out
        assert "ERROR: Missing binary: libc/0.1" in c.out

        c.run("install app -pr=profile --build=missing")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)

        # Check lockfile
        c.run("lock create app -pr=profile")
        lock = c.load("app/conan.lock")
        assert f"{pkg}#{rrev}" in lock

        # with lockfile
        c.run("install app -pr=profile")
        c.assert_listed_require({f"{pkg}#{rrev}": "Cache"}, build=tool_require)


@pytest.mark.parametrize("pattern, replace", [
    ("pkg", "pkg/0.1"),
    ("pkg/*", "pkg"),
    ("pkg/*:pid1", "pkg/0.1"),
    ("pkg/*:pid1", "pkg/0.1:pid2"),
    ("pkg/*", "pkg/0.1:pid2"),
    (":", ""),
    ("pkg/version:pid", ""),
    ("pkg/version:pid", ":")
])
def test_replace_requires_errors(pattern, replace):
    c = TestClient(light=True)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.2"),
            "profile": f"[replace_requires]\n{pattern}: {replace}"})
    c.run("create pkg")
    c.run("install app -pr=profile", assert_error=True)
    assert "ERROR: Error reading 'profile' profile: Error in [replace_xxx]" in c.out


def test_replace_requires_invalid_requires_errors():
    """
    replacing for something incorrect not existing is not an error per-se, it is valid that
    a recipe requires("pkg/2.*"), and then it will fail because such package doesn't exist
    """
    c = TestClient(light=True)
    c.save({"app/conanfile.py": GenConanfile().with_requires("pkg/0.2"),
            "profile": f"[replace_requires]\npkg/0.2: pkg/2.*"})
    c.run("install app -pr=profile", assert_error=True)
    assert "pkg/0.2: pkg/2.*" in c.out  # The replacement happens
    assert "ERROR: Package 'pkg/2.*' not resolved" in c.out


def test_replace_requires_json_format():
    c = TestClient(light=True)
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.2"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.1"),
            "profile": f"[replace_requires]\npkg/0.1: pkg/0.2"})
    c.run("create pkg")
    c.run("install app -pr=profile --format=json")
    assert "pkg/0.1: pkg/0.2" in c.out  # The replacement happens
    graph = json.loads(c.stdout)
    assert graph["graph"]["replaced_requires"] == {"pkg/0.1": "pkg/0.2"}


def test_replace_requires_test_requires():
    c = TestClient(light=True)
    c.save({"gtest/conanfile.py": GenConanfile("gtest", "0.2"),
            "app/conanfile.py": GenConanfile().with_test_requires("gtest/0.1"),
            "profile": f"[replace_requires]\ngtest/0.1: gtest/0.2"})
    c.run("create gtest")
    c.run("install app -pr=profile")
    assert "gtest/0.1: gtest/0.2" in c.out  # The replacement happens
