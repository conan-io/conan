import pytest

from conans.model.recipe_ref import RecipeReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save


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
])
@pytest.mark.parametrize("tool_require", [False, True])
class TestReplaceRequires:
    def test_alternative(self, tool_require, require, pattern, alternative, pkg):
        c = TestClient()
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
        c.run("install pkg -pr=profile")
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
        c = TestClient()
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
])
def test_replace_requires_errors(pattern, replace):
    c = TestClient()
    c.save({"pkg/conanfile.py": GenConanfile("pkg", "0.1"),
            "app/conanfile.py": GenConanfile().with_requires("pkg/0.2"),
            "profile": f"[replace_requires]\n{pattern}: {replace}"})
    c.run("create pkg")
    c.run("install app -pr=profile", assert_error=True)
    assert f"ERROR: Error reading 'profile' profile. Error in [replace_xxx] '{pattern}: {replace}'"
