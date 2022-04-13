import json

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


def test_cache_path_regular():

    t = TestClient()
    t.save({"conanfile.py": GenConanfile()})
    t.run("create . --name foo --version 1.0")
    pref = t.created_package_reference("foo/1.0")

    # By default, exports folder, works with pref
    t.run("cache path {}".format(pref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export()
    assert folder == str(t.out).rstrip()

    # By default, exports folder, works with ref
    t.run("cache path {}".format(pref.ref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export()
    assert folder == str(t.out).rstrip()

    # exports can be specified too
    t.run("cache path {} --folder exports".format(pref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export()
    assert folder == str(t.out).rstrip()

    # with reference works too
    t.run("cache path {} --folder exports".format(pref.ref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export()
    assert folder == str(t.out).rstrip()

    # exports_sources
    t.run("cache path {} --folder exports_sources".format(pref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export_sources()
    assert folder == str(t.out).rstrip()

    # with reference works too
    t.run("cache path {} --folder exports_sources".format(pref.ref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).export_sources()
    assert folder == str(t.out).rstrip()

    # sources
    t.run("cache path {} --folder sources".format(pref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).source()
    assert folder == str(t.out).rstrip()

    # with reference works too
    t.run("cache path {} --folder sources".format(pref.ref.repr_notime()))
    folder = t.cache.ref_layout(pref.ref).source()
    assert folder == str(t.out).rstrip()

    # build
    t.run("cache path {} --folder build".format(pref.repr_notime()))
    folder = t.cache.pkg_layout(pref).build()
    assert folder == str(t.out).rstrip()

    # package
    t.run("cache path {} --folder package".format(pref.repr_notime()))
    folder = t.cache.pkg_layout(pref).package()
    assert folder == str(t.out).rstrip()

    # Errors

    # build, cannot obtain build without pref
    t.run("cache path {} --folder build".format(pref.ref.repr_notime()), assert_error=True)
    assert "ERROR: '--folder build' requires a valid package reference" in t.out

    # package, cannot obtain package without pref
    t.run("cache path {} --folder package".format(pref.ref.repr_notime()), assert_error=True)
    assert "ERROR: '--folder package' requires a valid package reference" in t.out

    # Invalid reference
    t.run("cache path patata --folder package", assert_error=True)
    assert "ERROR: Invalid recipe or package reference, specify a complete reference" in t.out

    # Missing reference
    t.run("cache path patata/1.0#123123:123123123#123123123 --folder package", assert_error=True)
    assert "ERROR: No entry for package 'patata/1.0#123123:123123123#123123123'" in t.out

    t.run("cache path patata/1.0#123123", assert_error=True)
    assert "ERROR: No entry for recipe 'patata/1.0#123123'" in t.out

    # JSON output
    t.run("cache path {} --folder package --format json".format(pref.repr_notime()))
    data = json.loads(t.stdout)
    path = t.cache.pkg_layout(pref).package()
    assert data["ref"] == pref.repr_notime()
    assert data["folder"] == "package"
    assert data["path"] == path
