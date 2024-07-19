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
        assert "Conflict between math/1.0.1 and math/1.0 in the graph"
        assert "Conflict originates from ai/1.0"
