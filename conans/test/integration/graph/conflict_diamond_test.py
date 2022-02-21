import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class TestConflictDiamondTest:
    def test_basic(self):
        c = TestClient()
        c.save({"math/conanfile.py": GenConanfile("math"),
                "engine/conanfile.py": GenConanfile("engine", "1.0").with_requires("math/1.0"),
                "ai/conanfile.py": GenConanfile("ai", "1.0").with_requires("math/1.0.1"),
                "game/conanfile.py": GenConanfile("game", "1.0").with_requires("engine/1.0",
                                                                               "ai/1.0"),
                })
        c.run("create math --version=1.0")
        c.run("create math --version=1.0.1")
        c.run("create math --version=1.0.2")
        c.run("create engine")
        c.run("create ai")
        c.run("install game", assert_error=True)
        assert "version conflict" in c.out

        def _game_conanfile(version, reverse=False):
            if reverse:
                return GenConanfile("game", "1.0")\
                    .with_requirement(f"math/{version}", override=True)\
                    .with_requirement("engine/1.0")\
                    .with_requirement("ai/1.0")
            else:
                return GenConanfile("game", "1.0").with_requirement("engine/1.0") \
                    .with_requirement("ai/1.0") \
                    .with_requirement(f"math/{version}", override=True)

        for v in ("1.0", "1.0.1", "1.0.2"):
            c.save({"game/conanfile.py": _game_conanfile(v)})
            c.run("install game")
            c.assert_listed_require({f"math/{v}": "Cache"})

        # Check that order of requirements doesn't affect
        for v in ("1.0", "1.0.1", "1.0.2"):
            c.save({"game/conanfile.py": _game_conanfile(v, reverse=True)})
            c.run("install game")
            c.assert_listed_require({f"math/{v}": "Cache"})


@pytest.mark.xfail(reason="UX conflict error to be completed")
def test_create_werror():
    client = TestClient()
    client.save({"conanfile.py": """from conan import ConanFile
class Pkg(ConanFile):
pass
    """})
    client.run("export . --name=LibA --version=0.1 --user=user --channel=channel")
    client.run("export conanfile.py --name=LibA --version=0.2 --user=user --channel=channel")
    client.save({"conanfile.py": """from conan import ConanFile
class Pkg(ConanFile):
requires = "LibA/0.1@user/channel"
    """})
    client.run("export ./ --name=LibB --version=0.1 --user=user --channel=channel")
    client.save({"conanfile.py": """from conan import ConanFile
class Pkg(ConanFile):
requires = "LibA/0.2@user/channel"
    """})
    client.run("export . --name=LibC --version=0.1 --user=user --channel=channel")
    client.save({"conanfile.py": """from conan import ConanFile
class Pkg(ConanFile):
requires = "LibB/0.1@user/channel", "LibC/0.1@user/channel"
    """})
    client.run("create ./conanfile.py consumer/0.1@lasote/testing", assert_error=True)
    self.assertIn("ERROR: Conflict in LibC/0.1@user/channel",
                  client.out)
