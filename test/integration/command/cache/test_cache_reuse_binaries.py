import json
import os
import shutil

import pytest

from conan.api.model import PkgReference, RecipeReference
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer
from conan.internal.errors import ConanReferenceAlreadyExistsInDB
from conan.internal.util.files import load


def _recipe(version_tag="v1"):
    return GenConanfile("pkg", "1.0").with_settings("os") \
        .with_class_attribute(f"description = '{version_tag}'") \
        .with_package_file("bin/file.txt", "content!!")


def _two_revisions():
    """ pkg/1.0 with a binary in the first revision, and a second revision with no binaries """
    c = TestClient(light=True)
    c.save({"conanfile.py": _recipe("v1")})
    c.run("create . -s os=Linux")
    rrev1 = c.exported_recipe_revision()
    pref1 = c.created_package_reference("pkg/1.0")
    c.save({"conanfile.py": _recipe("v2")})
    c.run("export .")
    rrev2 = c.exported_recipe_revision()
    assert rrev1 != rrev2
    return c, rrev1, rrev2, pref1


def test_reuse_binaries_defaults():
    """ By default, the target is the latest revision, and the source the previous one """
    c, rrev1, rrev2, pref1 = _two_revisions()
    pkgid, prev = pref1.package_id, pref1.revision

    c.run("install --requires=pkg/1.0 -s os=Linux", assert_error=True)
    assert "ERROR: Missing binary: pkg/1.0" in c.out

    c.run("cache reuse-binaries pkg/1.0")
    assert f"Copying binaries from pkg/1.0#{rrev1} to pkg/1.0#{rrev2}" in c.out
    assert f"Copied {pkgid}#{prev}" in c.out
    assert "1 copied, 0 already existing, 0 dirty" in c.out

    # Same package_id and prev under both revisions
    c.run(f"list pkg/1.0#*:*#*")
    assert c.out.count(f"{pkgid}") == 2
    assert c.out.count(f"{prev}") == 2

    # And the binary is now directly usable
    c.run("install --requires=pkg/1.0 -s os=Linux")
    assert f"pkg/1.0#{rrev2}:{pkgid}#{prev} - Cache" in c.out

    # The copy is correct and independent
    c.run("cache check-integrity pkg/1.0#*:*#*")
    pref2 = PkgReference.loads(f"pkg/1.0#{rrev2}:{pkgid}#{prev}")
    pref1 = PkgReference.loads(f"pkg/1.0#{rrev1}:{pkgid}#{prev}")
    layout1 = c.get_latest_pkg_layout(pref1)
    layout2 = c.get_latest_pkg_layout(pref2)
    assert layout1.base_folder != layout2.base_folder
    assert load(os.path.join(layout2.package(), "bin", "file.txt")) == "content!!"

    # Removing the original revision doesn't affect the copy
    c.run(f"remove pkg/1.0#{rrev1} -c")
    c.run("install --requires=pkg/1.0 -s os=Linux")
    assert f"pkg/1.0#{rrev2}:{pkgid}#{prev} - Cache" in c.out


def test_reuse_binaries_explicit_revisions():
    c, rrev1, rrev2, pref1 = _two_revisions()
    pkgid, prev = pref1.package_id, pref1.revision
    # Even if the latest is rrev2, make the explicit target and source revision be used
    c.save({"conanfile.py": _recipe("v3")})
    c.run("export .")
    rrev3 = c.exported_recipe_revision()

    c.run(f"cache reuse-binaries pkg/1.0#{rrev2} --from-revision={rrev1}")
    assert f"Copying binaries from pkg/1.0#{rrev1} to pkg/1.0#{rrev2}" in c.out
    c.run(f"list pkg/1.0#{rrev2}:*")
    assert pkgid in c.out
    c.run(f"list pkg/1.0#{rrev3}:*")
    assert pkgid not in c.out

    # latest is rrev3, and by default the previous one is rrev2, that has the binary now
    c.run("cache reuse-binaries pkg/1.0")
    assert f"Copying binaries from pkg/1.0#{rrev2} to pkg/1.0#{rrev3}" in c.out
    assert "1 copied" in c.out


def test_reuse_binaries_json_output():
    c, rrev1, rrev2, pref1 = _two_revisions()
    c.run("cache reuse-binaries pkg/1.0 --format=json")
    result = json.loads(c.stdout)["Local Cache"]
    rrev_data = result["pkg/1.0"]["revisions"][rrev2]
    pkg_data = rrev_data["packages"][pref1.package_id]
    assert list(pkg_data["revisions"]) == [pref1.revision]


def test_reuse_binaries_idempotent_and_no_shadowing():
    c, rrev1, rrev2, pref1 = _two_revisions()
    c.run("cache reuse-binaries pkg/1.0")
    assert "1 copied" in c.out
    # Second time, nothing to do
    c.run("cache reuse-binaries pkg/1.0")
    assert "Skipped" in c.out
    assert "0 copied, 1 already existing" in c.out

    # A natively built binary in the target is never shadowed
    c.save({"conanfile.py": _recipe("v3")})
    c.run("create . -s os=Linux")
    rrev3 = c.exported_recipe_revision()
    native = c.created_package_reference("pkg/1.0")
    c.run(f"cache reuse-binaries pkg/1.0#{rrev3} --from-revision={rrev1}")
    assert "0 copied, 1 already existing" in c.out
    c.run(f"list pkg/1.0#{rrev3}:*#*")
    assert native.revision in c.out


def test_reuse_binaries_all_package_ids():
    c = TestClient(light=True)
    c.save({"conanfile.py": _recipe("v1")})
    c.run("create . -s os=Linux")
    linux = c.created_package_reference("pkg/1.0")
    c.run("create . -s os=Windows")
    windows = c.created_package_reference("pkg/1.0")
    c.save({"conanfile.py": _recipe("v2")})
    c.run("export .")
    rrev2 = c.exported_recipe_revision()

    c.run("cache reuse-binaries pkg/1.0")
    assert "2 copied" in c.out
    c.run(f"list pkg/1.0#{rrev2}:*")
    assert windows.package_id in c.out
    assert linux.package_id in c.out


def test_reuse_binaries_dirty_package_skipped():
    c, rrev1, rrev2, pref1 = _two_revisions()
    layout = c.get_latest_pkg_layout(pref1)
    layout_dirty = layout.package() + ".dirty"
    with open(layout_dirty, "w") as f:
        f.write("")
    c.run("cache reuse-binaries pkg/1.0")
    assert "the package is dirty" in c.out
    assert "0 copied, 0 already existing, 1 dirty" in c.out
    c.run(f"list pkg/1.0#{rrev2}:*")
    assert pref1.package_id not in c.out


def test_reuse_binaries_errors():
    c = TestClient(light=True)
    c.save({"conanfile.py": _recipe("v1")})
    c.run("create . -s os=Linux")
    rrev1 = c.exported_recipe_revision()

    c.run("cache reuse-binaries pkg/1.0", assert_error=True)
    assert "There is no previous revision of 'pkg/1.0#" in c.out
    c.run("cache reuse-binaries other/1.0", assert_error=True)
    assert "Recipe 'other/1.0' not found" in c.out
    c.run("cache reuse-binaries pkg/1.0#nonexisting", assert_error=True)
    assert "Recipe 'pkg/1.0#nonexisting' not found" in c.out

    c.save({"conanfile.py": _recipe("v2")})
    c.run("export .")
    c.run(f"cache reuse-binaries pkg/1.0 --from-revision={rrev1}x", assert_error=True)
    assert f"Recipe 'pkg/1.0#{rrev1}x' not found" in c.out
    c.run(f"cache reuse-binaries pkg/1.0#{rrev1} --from-revision={rrev1}", assert_error=True)
    assert "The source and target recipe revisions are the same" in c.out


@pytest.mark.parametrize("package_id_changes", [False, True])
def test_reuse_binaries_package_id_mismatch(package_id_changes):
    """ If the new recipe revision computes a different package_id, the copy is harmless but it
    is never used """
    c = TestClient(light=True)
    c.save({"conanfile.py": _recipe("v1")})
    c.run("create . -s os=Linux")
    pref1 = c.created_package_reference("pkg/1.0")
    new_recipe = _recipe("v2")
    if package_id_changes:
        new_recipe = new_recipe.with_option("shared", [True, False]) \
            .with_default_option("shared", False)
    c.save({"conanfile.py": new_recipe})
    c.run("export .")
    rrev2 = c.exported_recipe_revision()
    c.run("cache reuse-binaries pkg/1.0")
    c.run("install --requires=pkg/1.0 -s os=Linux", assert_error=package_id_changes)
    if package_id_changes:
        assert "ERROR: Missing binary: pkg/1.0" in c.out
    else:
        assert f"pkg/1.0#{rrev2}:{pref1.package_id}#{pref1.revision} - Cache" in c.out


def test_reuse_binaries_upload():
    """ The output can be directly used to upload the binaries of the new revision """
    server = TestServer()
    c = TestClient(servers={"default": server}, inputs=["admin", "password"], light=True)
    c.save({"conanfile.py": _recipe("v1")})
    c.run("create . -s os=Linux")
    pref1 = c.created_package_reference("pkg/1.0")
    c.save({"conanfile.py": _recipe("v2")})
    c.run("export .")
    rrev2 = c.exported_recipe_revision()

    c.run("cache reuse-binaries pkg/1.0 --format=json", redirect_stdout="list.json")
    c.run("upload --list=list.json -r=default")
    c2 = TestClient(servers={"default": server}, inputs=["admin", "password"], light=True)
    c2.run(f"list pkg/1.0#{rrev2}:*#* -r=default")
    assert pref1.package_id in c2.out
    assert pref1.revision in c2.out
    c2.run("install --requires=pkg/1.0 -s os=Linux")
    assert f"pkg/1.0#{rrev2}:{pref1.package_id}#{pref1.revision} - Download (default)" in c2.out


def test_copy_pkg_layout_failures(monkeypatch):
    """ A failed copy doesn't leave anything behind, and copying an existing package doesn't
    touch it """
    c, rrev1, rrev2, pref1 = _two_revisions()
    cache = c.cache
    src_layout = c.get_latest_pkg_layout(pref1)
    target = cache.get_latest_recipe_revision(RecipeReference.loads("pkg/1.0"))
    assert target.revision == rrev2

    def failing_copytree(*args, **kwargs):
        raise OSError("Simulated failure while copying")

    with monkeypatch.context() as m:
        m.setattr(shutil, "copytree", failing_copytree)
        with pytest.raises(OSError, match="Simulated failure"):
            cache.copy_pkg_layout(src_layout, target)
    assert cache.get_package_references(target) == []

    new_pref = cache.copy_pkg_layout(src_layout, target)
    new_layout = cache.pkg_layout(new_pref)
    assert not new_layout.package_is_dirty()
    assert load(os.path.join(new_layout.package(), "bin", "file.txt")) == "content!!"
    with pytest.raises(ConanReferenceAlreadyExistsInDB):
        cache.copy_pkg_layout(src_layout, target)
    assert load(os.path.join(new_layout.package(), "bin", "file.txt")) == "content!!"
    assert len(cache.get_package_references(target)) == 1
