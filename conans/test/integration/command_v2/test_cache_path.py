import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


@pytest.fixture(scope="module")
def created_package():
    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name foo --version 1.0")
    pref = t.created_package_reference("foo/1.0")
    return t, pref


def test_cache_path(created_package):
    t, pref = created_package
    recipe_revision = pref.ref.revision

    # Basic recipe paths, without specifying revision
    recipe_layout = t.cache.ref_layout(pref.ref)
    t.run("cache path foo/1.0")
    assert recipe_layout.export() == str(t.out).rstrip()
    t.run("cache path foo/1.0#latest")
    assert recipe_layout.export() == str(t.out).rstrip()
    t.run("cache path foo/1.0 --folder=export_source")
    assert recipe_layout.export_sources() == str(t.out).rstrip()
    t.run("cache path foo/1.0 --folder=source")
    assert recipe_layout.source() == str(t.out).rstrip()

    # Basic recipe paths, with revision
    t.run(f"cache path foo/1.0#{recipe_revision}")
    assert recipe_layout.export() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0#{recipe_revision} --folder=export_source")
    assert recipe_layout.export_sources() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0#{recipe_revision} --folder=source")
    assert recipe_layout.source() == str(t.out).rstrip()

    pkg_layout = t.cache.pkg_layout(pref)
    # Basic package paths, without specifying revision
    t.run(f"cache path foo/1.0:{pref.package_id}")
    assert pkg_layout.package() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0:{pref.package_id} --folder=build")
    assert pkg_layout.build() == str(t.out).rstrip()

    # Basic package paths, with recipe-revision
    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id}")
    assert pkg_layout.package() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id}#latest")
    assert pkg_layout.package() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id} --folder=build")
    assert pkg_layout.build() == str(t.out).rstrip()

    # Basic package paths, with both revisions
    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id}#{pref.revision}")
    assert pkg_layout.package() == str(t.out).rstrip()
    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id}#{pref.revision} --folder=build")
    assert pkg_layout.build() == str(t.out).rstrip()


def test_cache_path_exist_errors(created_package):
    t, pref = created_package
    recipe_revision = pref.ref.revision

    t.run("cache path nonexist/1.0", assert_error=True)
    assert "ERROR: 'nonexist/1.0' not found in cache" in t.out

    t.run("cache path nonexist/1.0#rev", assert_error=True)
    # TODO: Improve this error message
    assert "ERROR: No entry for recipe 'nonexist/1.0#rev'" in t.out

    t.run("cache path foo/1.0#rev", assert_error=True)
    # TODO: Improve this error message
    assert "ERROR: No entry for recipe 'foo/1.0#rev'" in t.out

    t.run(f"cache path foo/1.0:pid1", assert_error=True)
    assert f"ERROR: 'foo/1.0#{recipe_revision}:pid1' not found in cache" in t.out

    t.run(f"cache path foo/1.0#{recipe_revision}:pid1", assert_error=True)
    assert f"ERROR: 'foo/1.0#{recipe_revision}:pid1' not found in cache" in t.out

    t.run(f"cache path foo/1.0#{recipe_revision}:{pref.package_id}#rev2", assert_error=True)
    assert f"ERROR: No entry for package 'foo/1.0#{recipe_revision}:{pref.package_id}#rev2" in t.out


def test_cache_path_arg_errors():
    t = TestClient()
    # build, cannot obtain build without pref
    t.run("cache path foo/1.0 --folder build", assert_error=True)
    assert "ERROR: '--folder build' requires a valid package reference" in t.out

    # Invalid reference
    t.run("cache path patata", assert_error=True)
    assert "ERROR: patata is not a valid recipe reference" in t.out

    # source, cannot obtain build without pref
    t.run("cache path foo/1.0:pid --folder source", assert_error=True)
    assert "ERROR: '--folder source' requires a recipe reference" in t.out
