from conans.model.package_ref import PkgReference


def test_package_reference():
    r = PkgReference.loads("pkg/0.1:pkgid1")
    assert r.ref.name == "pkg"
    assert r.ref.version == "0.1"
    assert r.ref.user is None
    assert r.ref.channel is None
    assert r.ref.revision is None
    assert r.package_id == "pkgid1"
    assert r.revision is None
    assert str(r) == "pkg/0.1:pkgid1"
    assert repr(r) == "pkg/0.1:pkgid1"

    r = PkgReference.loads("pkg/0.1@user:pkgid1")
    assert r.ref.name == "pkg"
    assert r.ref.version == "0.1"
    assert r.ref.user == "user"
    assert r.ref.channel is None
    assert r.ref.revision is None
    assert r.package_id == "pkgid1"
    assert r.revision is None
    assert str(r) == "pkg/0.1@user:pkgid1"
    assert repr(r) == "pkg/0.1@user:pkgid1"
