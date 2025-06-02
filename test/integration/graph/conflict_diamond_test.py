import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class TestConflictDiamondTest:
    def test_version_diamond_conflict(self):
        """
        test that we obtain a version conflict with a diamond, and that we can fix it by
        defining an override in the "game" consumer
        game -> engine/1.0 -> math/1.0
          |---> ai/1.0 -----> math/1.0.1 (conflict)
        """
        c = TestClient(light=True)
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
        assert "Version conflict: Conflict between math/1.0.1 and math/1.0 in the graph" in c.out
        # This shouldnt error, so we are able to diagnose our dependency graph
        # The UX still need to be improved, but this is start
        c.run("graph info game --filter=requires", assert_error=True)
        assert "math/1.0" in c.out

        def _game_conanfile(version, reverse=False):
            if reverse:
                """
                 game ---(override)--_> math/newversion
                    |---> engine/1.0 -> math/1.0
                    |---> ai/1.0 -----> math/1.0.1 (conflict solved by override)
                """
                return GenConanfile("game", "1.0")\
                    .with_requirement(f"math/{version}", override=True)\
                    .with_requirement("engine/1.0")\
                    .with_requirement("ai/1.0")
            else:
                """
                game --> engine/1.0 -> math/1.0
                   |---> ai/1.0 -----> math/1.0.1 (conflict solved by override)
                   |---(override)--_> math/newversion
                """
                return GenConanfile("game", "1.0").with_requirement("engine/1.0") \
                    .with_requirement("ai/1.0") \
                    .with_requirement(f"math/{version}", override=True)

        for v in ("1.0", "1.0.1", "1.0.2"):
            c.save({"game/conanfile.py": _game_conanfile(v)})
            c.run("install game")
            c.assert_overrides({"math/1.0": [f"math/{v}"],
                                "math/1.0.1": [f"math/{v}"]})
            c.assert_listed_require({f"math/{v}": "Cache"})

        # Check that order of requirements doesn't affect
        for v in ("1.0", "1.0.1", "1.0.2"):
            c.save({"game/conanfile.py": _game_conanfile(v, reverse=True)})
            c.run("install game")
            c.assert_overrides({"math/1.0": [f"math/{v}"],
                                "math/1.0.1": [f"math/{v}"]})
            c.assert_listed_require({f"math/{v}": "Cache"})

        c.run("install --requires=engine/1.0  --requires=ai/1.0", assert_error=True)
        assert "Conflict between math/1.0.1 and math/1.0 in the graph" in c.out
        assert "Conflict originates from ai/1.0" in c.out


@pytest.mark.parametrize("version_range", [True, False])
def test_conflict_user(version_range):
    # https://github.com/conan-io/conan/issues/17875
    v = "[^1.0]" if version_range else "1.0"
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires(f"dep/{v}@user1"),
            "app/conanfile.py": GenConanfile("app", "1.0").with_requires(f"pkg/{v}@user1",
                                                                         f"dep/{v}@user2")})
    c.run("create dep --user=user1")
    c.run("create dep --user=user2")
    c.run("create pkg --user=user1")
    c.run("install app", assert_error=True)
    assert f"Version conflict: Conflict between dep/{v}@user1 and dep/{v}@user2" in c.out


def test_conflict_user_order():
    # https://github.com/conan-io/conan/issues/17875
    c = TestClient(light=True)
    c.save({"dep/conanfile.py": GenConanfile("dep", "1.0"),
            "pkg/conanfile.py": GenConanfile("pkg", "1.0").with_requires("dep/1.0@user1"),
            "app/conanfile.py": GenConanfile("app", "1.0").with_requires("pkg/1.0@user1",
                                                                         "dep/[>=1.0]@user2")})
    c.run("create dep --user=user1")
    c.run("create dep --user=user2")
    c.run("create pkg --user=user1")
    c.run("install app", assert_error=True)
    assert "ERROR: Version conflict: Conflict between dep/1.0@user1 and dep/[>=1.0]@user2" in c.out

def test_header_only_conflict_when_not_visible():
    tc = TestClient(light=True)
    tc.save({"pkg4/conanfile.py": GenConanfile("pkg4", "1.0")
                .with_package_type("header-library"),
             "pkg3/conanfile.py": GenConanfile("pkg3")
                .with_package_type("header-library")
                .with_requires("pkg4/1.0"),
             # pkg existence is necessary, without it a conflict is found
             "pkg2/conanfile.py": GenConanfile("pkg2", "1.0")
                .with_package_type("header-library")
                # Both this and the requires in the info need to be 1.1 not to trigger the conflict
                # Using 3.0 in both generates a disconnected graph
                .with_requirement("pkg3/1.1"),
             "pkg1/conanfile.py": GenConanfile("pkg1", "1.0")
                .with_package_type("static-library")
                # The order here is important, conan reports a conflict with the inverse order
                # The visible=False here is also important, otherwise the conflict is detected
                .with_requirement("pkg3/1.0", visible=False)
                .with_requirement("pkg2/1.0")})
    tc.run("create pkg4")
    tc.run("create pkg3 --version=1.0")
    tc.run("create pkg3 --version=1.1")
    tc.run("create pkg2")
    # Creating this pkg1 does generate a conflict
    tc.run("export pkg1")
    tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0 --build=missing", assert_error=True)
    assert "Conflict between pkg3/1.1 and pkg3/1.0" in tc.out
