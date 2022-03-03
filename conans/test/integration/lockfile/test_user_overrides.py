from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


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

    c.run("lock add --requires=math/1.0 --requires=unrelated/2.0 --lockfile-out=conan.lock")
    c.run("graph info game --lockfile=conan.lock --lockfile-out=new.lock")
    assert "math/1.0" in c.out
    assert "math/1.2" not in c.out

    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "math/1.0#8e1a7a5ce869d8c54ae3d33468fd657" in new_lock

    # Repeat for 1.1
    c.run("lock add --requires=math/1.1 --requires=unrelated/2.0 --lockfile-out=conan.lock")
    c.run("graph info game --lockfile=conan.lock --lockfile-out=new.lock")
    assert "math/1.1" in c.out
    assert "math/1.0" not in c.out

    # The resulting lockfile contains the full revision now
    new_lock = c.load("new.lock")
    assert "math/1.1#8e1a7a5ce869d8c54ae3d33468fd657" in new_lock
