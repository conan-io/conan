import json

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_no_explicit_underscore_requires():
    """ https://github.com/conan-io/conan/issues/20361

    Explicitly using "_" as user/channel in --requires/--tool-requires is forbidden, as it
    is a protocol-level placeholder reserved to mean "no user/channel", and was creating
    duplicated recipe references in the cache (same recipe, 2 different identities).
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile("foobar", "1.0.0")})
    c.run("export-pkg .")
    c.run("upload foobar/1.0.0 -r=default -c")
    c.run("remove * -c")

    # The "normal" way, without user/channel, keeps working fine
    c.run("install --requires=foobar/1.0.0")

    error_msg = "Invalid package user/channel"
    # But explicitly typing the "_" placeholder is now forbidden
    c.run("install --requires=foobar/1.0.0@_", assert_error=True)
    assert error_msg in c.out
    c.run("install --requires=foobar/1.0.0@_/_", assert_error=True)
    assert error_msg in c.out
    c.run("install --tool-requires=foobar/1.0.0@_", assert_error=True)
    assert error_msg in c.out

    # Only one single recipe reference exists in the cache
    c.run("list * --format=json", redirect_stdout="pkglist.json")
    pkglist = json.loads(c.load("pkglist.json"))
    assert list(pkglist["Local Cache"].keys()) == ["foobar/1.0.0"]


def test_no_explicit_underscore_export():
    """ Explicitly exporting/creating a recipe with user/channel "_" is forbidden too """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("foobar", "1.0.0")})
    c.run("export . --user=_", assert_error=True)
    assert "ERROR: Invalid package user '_'" in c.out
    c.run("export . --user=foo --channel=_", assert_error=True)
    assert "ERROR: Invalid package channel '_'" in c.out


def test_no_explicit_underscore_conanfile_requires():
    c = TestClient()
    c.save({"foobar/conanfile.py": GenConanfile("foobar", "1.0.0"),
                 "consumer/conanfile.py": GenConanfile("consumer", "1.0")
                .with_requires("foobar/1.0.0@_")})
    c.run("export foobar")
    c.run("install consumer", assert_error=True)
    assert "ERROR: Package 'foobar/1.0.0@_'" in c.out
