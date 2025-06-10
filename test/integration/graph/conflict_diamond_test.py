import json

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


class TestErrorVisibleFalse:

    @pytest.mark.parametrize("order", [True, False])
    def test_subgraph_conflict(self, order):
        #  cli--> pkg1/1.0 -(visible=False) --------------> pkg3/1.0 (conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.1 (conflict)
        # This conflict is good, the default dependencies are incompatible in definition
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg1/1.0", assert_error=True)
        assert "ERROR: Version conflict: Conflict between pkg3/1.1 and pkg3/1.0" in tc.out

    @pytest.mark.parametrize("order", [True, False])
    def test_subgraph_no_conflict(self, order):
        #  cli--> pkg1/1.0 -(visible=False) --------------> pkg3/1.0 (no conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.0 (no conflict)
        # This doesn't conflict, but package topology is affected, converging to a direct dependency
        # of a visible one
        #  cli--> pkg1/1.0 -(visible=True) --------------> pkg3/1.0 (no conflict)
        #             \----> pkg2/1.0 ----------------------/
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.0"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg2")
        tc.run("export pkg1")

        tc.run("graph info --requires=pkg1/1.0 --format=json")
        assert ("pkg1/1.0: WARN: risk: This package has 2 different dependencies on pkg3/1.0 "
                "with different visibility. This is an ill-formed graph") in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 4  # Including the CLI 0-3
        pkg1 = graph["graph"]["nodes"]["1"]
        deps = pkg1["dependencies"]
        assert len(deps) == 2
        if order:
            assert pkg1["ref"] == "pkg1/1.0#0500746058caef3211f77104e0b13b12"
            dep_pkg2 = deps["3"]
            dep_pkg3 = deps["2"]
        else:
            assert pkg1["ref"] == "pkg1/1.0#35693f0161f7c150aa3e86f5d13e77b1"
            dep_pkg2 = deps["2"]
            dep_pkg3 = deps["3"]
        assert dep_pkg2["ref"] == "pkg2/1.0"
        assert dep_pkg2["visible"] is True
        assert dep_pkg3["ref"] == "pkg3/1.0"
        assert dep_pkg2["visible"] is True

    @pytest.mark.parametrize("order", [True, False])
    def test_transitive_conflict(self, order):
        # cli --------------------------------------------> pkg3/1.1
        #   \--> pkg1/1.0 -(visible=False) -> pkg3/1.0 (conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.1 (no conflict)
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0", assert_error=True)
        # TODO: The error conflict is different, still better than nothing
        if order:
            assert "ERROR: Runtime Conflict Error: There is a conflict between packages " in tc.out
        else:
            assert "ERROR: Version conflict: Conflict between pkg3/1.0 and pkg3/1.1" in tc.out

    @pytest.mark.parametrize("order", [True, False])
    def test_transitive_version_range_no_conflict(self, order):
        # if in the case above, we use a version-range, we can avoid the conflict
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/[*]", visible=False).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/[*]", visible=False)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0 --format=json")
        assert ("pkg1/1.0: WARN: risk: This package has 2 different dependencies on pkg3/1.1 "
                "with different visibility. This is an ill-formed graph") in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 4  # FIXME: Orphan!!!
        pkg1 = graph["graph"]["nodes"]["2"]
        deps = pkg1["dependencies"]
        assert len(deps) == 2
        if order:
            assert pkg1["ref"] == "pkg1/1.0#49dcd0519757b43aec3907d6c2a68c2f"
        else:
            assert pkg1["ref"] == "pkg1/1.0#b49fcee999d981b22021b0c80d92b122"
        dep_pkg2 = deps["3"]
        dep_pkg3 = deps["1"]
        assert dep_pkg2["ref"] == "pkg2/1.0"
        assert dep_pkg2["visible"] is True
        assert dep_pkg3["ref"] == "pkg3/1.1"
        assert dep_pkg2["visible"] is True
