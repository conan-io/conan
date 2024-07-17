import json
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_user_overrides():
    """ Show that it is possible to add things to lockfiles, to pre-lock things explicitly from
    user side
    """
    c = TestClient()
    c.save({"math/conanfile.py": GenConanfile("math"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("math/[*]"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_requires("engine/[*]")})

    c.run("export math --version=1.0")
    c.run("export math --version=1.1")
    c.run("export math --version=1.2")
    c.run("export engine")

    c.run("graph info game")
    assert "math/1.2" in c.out
    assert "math/1.0" not in c.out

    c.run("lock add --requires=math/1.0 --requires=unrelated/2.0")
    c.run("graph info game --lockfile=conan.lock --lockfile-out=new.lock --lockfile-partial")
    assert "math/1.0" in c.out
    assert "math/1.2" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "math/1.0#8e1a7a5ce869d8c54ae3d33468fd657" in new_lock

    # Repeat for 1.1
    c.run("lock add --requires=math/1.1 --requires=unrelated/2.0")
    c.run("graph info game --lockfile=conan.lock --lockfile-partial --lockfile-out=new.lock")
    assert "math/1.1" in c.out
    assert "math/1.0" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "math/1.1#8e1a7a5ce869d8c54ae3d33468fd657" in new_lock


def test_user_build_overrides():
    """ Test that it is possible to lock also build-requries
    """
    c = TestClient()
    c.save({"cmake/conanfile.py": GenConanfile("cmake"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_build_requires("cmake/[*]")})

    c.run("export cmake --version=1.0")
    c.run("export cmake --version=1.1")
    c.run("export cmake --version=1.2")

    c.run("graph info engine")
    assert "cmake/1.2" in c.out
    assert "cmake/1.0" not in c.out

    c.run("lock add --build-requires=cmake/1.0")
    c.run("graph info engine --lockfile=conan.lock --lockfile-out=new.lock --lockfile-partial")
    assert "cmake/1.0" in c.out
    assert "cmake/1.2" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "cmake/1.0" in new_lock

    # Repeat for 1.1
    c.run("lock add --build-requires=cmake/1.1 --lockfile-out=conan.lock")
    c.run("graph info engine --lockfile=conan.lock --lockfile-out=new.lock --lockfile-partial")
    assert "cmake/1.1" in c.out
    assert "cmake/1.0" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "cmake/1.1" in new_lock


def test_user_python_overrides():
    """ Test that it is possible to lock also python-requries
    """
    c = TestClient()
    c.save({"pytool/conanfile.py": GenConanfile("pytool"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_python_requires("pytool/[*]")})

    c.run("export pytool --version=1.0")
    c.run("export pytool --version=1.1")
    c.run("export pytool --version=1.2")

    c.run("graph info engine")
    assert "pytool/1.2" in c.out
    assert "pytool/1.0" not in c.out

    c.run("lock add --python-requires=pytool/1.0 --lockfile-out=conan.lock")
    c.run("graph info engine --lockfile=conan.lock --lockfile-out=new.lock")
    assert "pytool/1.0" in c.out
    assert "pytool/1.2" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "pytool/1.0" in new_lock

    # Repeat for 1.1
    c.run("lock add --python-requires=pytool/1.1 --lockfile-out=conan.lock")
    c.run("graph info engine --lockfile=conan.lock --lockfile-out=new.lock")
    assert "pytool/1.1" in c.out
    assert "pytool/1.0" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "pytool/1.1" in new_lock


def test_config_overrides():
    """ Test that it is possible to lock also config-requires
    """
    c = TestClient()
    c.run("lock add --config-requires=config/1.0")
    assert json.loads(c.load("conan.lock"))["config_requires"] == ["config/1.0"]
    c.run("lock remove --config-requires=config/1.0")
    assert json.loads(c.load("conan.lock"))["config_requires"] == []


def test_add_revisions():
    """ Is it possible to add revisions explicitly too
    """
    c = TestClient()
    c.save({"math/conanfile.py": GenConanfile("math"),
            "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("math/[*]"),
            "game/conanfile.py": GenConanfile("game", "1.0").with_requires("engine/[*]")})

    c.run("export math --version=1.0")
    rev0 = c.exported_recipe_revision()
    c.save({"math/conanfile.py": GenConanfile("math").with_build_msg("New rev1")})
    c.run("export math --version=1.0")
    rev1 = c.exported_recipe_revision()
    c.save({"math/conanfile.py": GenConanfile("math").with_build_msg("New rev2")})
    c.run("export math --version=1.0")
    rev2 = c.exported_recipe_revision()

    c.run("export engine")
    c.run("graph info game")
    assert f"math/1.0#{rev2}" in c.out
    assert f"math/1.0#{rev1}" not in c.out

    # without revision, it will resolve to latest
    c.run("lock add --requires=math/1.0 --requires=unrelated/2.0")
    c.run("graph info game --lockfile=conan.lock --lockfile-out=new.lock --lockfile-partial")
    assert f"math/1.0#{rev2}" in c.out
    assert f"math/1.0#{rev1}" not in c.out
    assert f"math/1.0#{rev0}" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert f"math/1.0#{rev2}" in new_lock
    assert f"math/1.0#{rev1}" not in new_lock
    assert f"math/1.0#{rev0}" not in c.out

    # with revision, it will resolve to that revision
    c.run(f"lock add --requires=math/1.0#{rev1} --requires=unrelated/2.0")
    c.run("graph info game --lockfile=conan.lock --lockfile-out=new.lock --lockfile-partial")
    assert f"math/1.0#{rev1}" in c.out
    assert f"math/1.0#{rev2}" not in c.out
    assert f"math/1.0#{rev0}" not in c.out
    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert f"math/1.0#{rev1}" in new_lock
    assert f"math/1.0#{rev2}" not in new_lock
    assert f"math/1.0#{rev0}" not in c.out


def test_add_multiple_revisions():
    """ What if we add multiple revisions, mix with and without revisions, with and without
    timestamps and it will not crash
    """
    c = TestClient()
    # without revision, it will resolve to latest
    c.run("lock add --requires=math/1.0#rev1")
    new_lock = c.load("conan.lock")
    assert "math/1.0#rev1" in new_lock

    c.run("lock add --requires=math/1.0#rev2")
    new_lock = json.loads(c.load("conan.lock"))
    assert ["math/1.0#rev2", "math/1.0#rev1"] == new_lock["requires"]
    c.run("lock add --requires=math/1.0#rev0")
    new_lock = json.loads(c.load("conan.lock"))
    assert ['math/1.0#rev2', 'math/1.0#rev1', 'math/1.0#rev0'] == new_lock["requires"]
    c.run("lock add --requires=math/1.0#revx%0.0")
    new_lock = json.loads(c.load("conan.lock"))
    assert ['math/1.0#revx%0.0', 'math/1.0#rev2', 'math/1.0#rev1', 'math/1.0#rev0'] == \
           new_lock["requires"]

    c.save({"conanfile.txt": ""})
    c.run("install . --lockfile=conan.lock")  # Just check that it doesn't crash
    c.run("install . --lockfile=conan.lock --lockfile-out=new.lock")
    new_lock = json.loads(c.load("conan.lock"))
    assert ['math/1.0#revx%0.0', 'math/1.0#rev2', 'math/1.0#rev1', 'math/1.0#rev0'] == \
           new_lock["requires"]

    # add without revision at all, will give us an error, as it doesn't make sense
    c.run("lock add --requires=math/1.0", assert_error=True)
    assert "Cannot add math/1.0 to lockfile, already exists" in c.out
    new_lock = json.loads(c.load("conan.lock"))
    assert ['math/1.0#revx%0.0', 'math/1.0#rev2', 'math/1.0#rev1', 'math/1.0#rev0'] == \
           new_lock["requires"]


def test_timestamps_are_updated():
    """ When ``conan lock add`` adds a revision with a timestamp, or without it, it will be
    updated in the lockfile-out to the resolved new timestamp
    """
    c = TestClient()
    c.save({"conanfile.txt": "[requires]\nmath/1.0",
            "math/conanfile.py": GenConanfile("math", "1.0")})
    c.run("create math")
    rev = c.exported_recipe_revision()
    # Create a new lockfile, wipe the previous
    c.run(f"lock add --lockfile=\"\" --requires=math/1.0#{rev}%0.123")
    c.run("install . --lockfile=conan.lock --lockfile-out=conan.lock")
    assert f" math/1.0#{rev} - Cache" in c.out
    new_lock = c.load("conan.lock")
    assert "%0.123" not in new_lock


def test_lock_add_error():
    # https://github.com/conan-io/conan/issues/14465
    c = TestClient()
    c.run(f"lock add --requires=math/1.0:pid1", assert_error=True)
    assert "ERROR: Invalid recipe reference 'math/1.0:pid1' is a package reference" in c.out


class TestLockRemove:
    @pytest.mark.parametrize("args, removed", [
        ("--requires=math/*", ["math"]),
        ("--requires=math/2.0", []),
        ("--build-requires=cmake/1.0", ["cmake"]),
        # Not valid ("--build-requires=*", ["cmake", "ninja"]),
        ("--build-requires=*/*", ["cmake", "ninja"]),  # But this is valid
        ("--python-requires=mytool/*", ["mytool"]),
        ("--python-requires=*tool/*", ["mytool", "othertool"]),
        # With version ranges
        ('--requires="math/[>=1.0 <2]"', ["math"]),
        ('--requires="math/[>1.0]"', []),
        ('--requires="*/[>=1.0 <2]"', ["math", "engine"])
    ])
    def test_lock_remove(self, args, removed):
        c = TestClient()
        lock = textwrap.dedent("""\
            {
                "version": "0.5",
                "requires": [
                    "math/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "math/1.0#12345%1702683584.3411012",
                    "engine/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ],
                "build_requires": [
                    "cmake/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "ninja/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ],
                "python_requires": [
                    "mytool/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "othertool/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ]
            }
            """)
        c.save({"conan.lock": lock})
        c.run(f"lock remove {args}")
        lock = c.load("conan.lock")
        for remove in removed:
            assert remove not in lock
        for pkg in {"math", "engine", "cmake", "ninja", "mytool", "othertool"}.difference(removed):
            assert pkg in lock

    @pytest.mark.parametrize("args, removed", [
        ("--requires=math/1.0#12345*", ["math/1.0#123456789abcdef"]),
        ("--requires=math/1.0#*", ["math/1.0#123456789abcdef",
                                   "math/1.0#85d927a4a067a531b1a9c7619522c015"]),
    ])
    def test_lock_remove_revisions(self, args, removed):
        c = TestClient()
        lock = textwrap.dedent("""\
            {
                "version": "0.5",
                "requires": [
                    "math/1.0#123456789abcdef%1702683584.3411012",
                    "math/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "engine/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ]
            }
            """)
        c.save({"conan.lock": lock})
        c.run(f"lock remove {args}")
        lock = c.load("conan.lock")
        for remove in removed:
            assert remove not in lock
        for pkg in {"math/1.0#123456789abcdef",
                    "math/1.0#85d927a4a067a531b1a9c7619522c015",
                    "engine/1.0#fd2b006646a54397c16a1478ac4111ac"}.difference(removed):
            assert pkg in lock

    @pytest.mark.parametrize("args, removed", [
        ("--requires=*/*@team", ["pkg/1.0@team"]),
        ("--requires=*/*@team*", ["pkg/1.0@team", "math/2.0@team/stable"]),
        ("--requires=*/*@user", ["math/1.0@user", "other/1.0@user"]),
        ("--requires=*/*@", ["engine/1.0"]),  # Remove those without user
        # with version ranges
        ("--requires=math/[*]@user", ["math/1.0@user"]),
        ("--requires=math/[*]@team*", ["math/2.0@team/stable"]),
    ])
    def test_lock_remove_user_channel(self, args, removed):
        c = TestClient()
        lock = textwrap.dedent("""\
            {
                "version": "0.5",
                "requires": [
                    "math/1.0@user#123456789abcdef%1702683584.3411012",
                    "math/2.0@team/stable#123456789abcdef%1702683584.3411012",
                    "other/1.0@user#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "pkg/1.0@team#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "engine/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ]
            }
            """)
        c.save({"conan.lock": lock})
        c.run(f"lock remove {args}")
        lock = c.load("conan.lock")
        for remove in removed:
            assert remove not in lock
        rest = {"math/1.0@user", "math/2.0@team/stable",
                "other/1.0@user", "pkg/1.0@team", "engine/1.0"}.difference(removed)
        for pkg in rest:
            assert pkg in lock


class TestLockUpdate:
    @pytest.mark.parametrize("kind, old, new", [
        ("requires", "math/1.0", "math/1.1"),
        ("build-requires", "cmake/1.0", "cmake/1.1"),
        ("python-requires", "mytool/1.0", "mytool/1.1"),
    ])
    def test_lock_update(self, kind, old, new):
        c = TestClient()
        lock = textwrap.dedent("""\
            {
                "version": "0.5",
                "requires": [
                    "math/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "math/1.0#12345%1702683584.3411012",
                    "engine/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ],
                "build_requires": [
                    "cmake/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "ninja/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ],
                "python_requires": [
                    "mytool/1.0#85d927a4a067a531b1a9c7619522c015%1702683583.3411012",
                    "othertool/1.0#fd2b006646a54397c16a1478ac4111ac%1702683583.3544693"
                ]
            }
            """)
        c.save({"conan.lock": lock})
        c.run(f"lock update --{kind}={new}")
        lock = c.load("conan.lock")
        assert old not in lock
        assert new in lock
