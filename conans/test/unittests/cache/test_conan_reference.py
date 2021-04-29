from conan.cache.conan_reference import ConanReference
from conans.model.ref import ConanFileReference


def test_loads():
    ref = ConanReference.loads('name/version#rrev:pkgid#prev')
    assert ref.name == "name"
    assert ref.version == "version"
    assert not ref.user
    assert not ref.channel
    assert ref.rrev == "rrev"
    assert ref.pkgid == "pkgid"
    assert ref.prev == "prev"

    ref = ConanReference.loads('name/version#rrev')
    assert ref.name == "name"
    assert ref.version == "version"
    assert not ref.user
    assert not ref.channel
    assert ref.rrev == "rrev"
    assert not ref.pkgid
    assert not ref.prev

    ref = ConanReference.loads('name/version@user/channel#rrev:pkgid#prev')
    assert ref.name == "name"
    assert ref.version == "version"
    assert ref.user == "user"
    assert ref.channel == "channel"
    assert ref.rrev == "rrev"
    assert ref.pkgid == "pkgid"
    assert ref.prev == "prev"

    ref = ConanReference.loads('name/version@user/channel#rrev')
    assert ref.name == "name"
    assert ref.version == "version"
    assert ref.user == "user"
    assert ref.channel == "channel"
    assert ref.rrev == "rrev"
    assert not ref.pkgid
    assert not ref.prev
