import json
import os

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


@pytest.mark.parametrize("test", [True, False])
@pytest.mark.parametrize("order", [True, False])
class TestErrorVisibleFalse:

    def test_subgraph_conflict(self, order, test):
        #  cli--> pkg1/1.0 -(visible=False) --------------> pkg3/1.0 (conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.1 (conflict)
        # This conflict is good, the default dependencies are incompatible in definition
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False, test=test).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False, test=test)
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

    def test_subgraph_conflict_second_level(self, order, test):
        #  cli--> pkg1/1.0 -(visible=False) ---> gtest/1.0 -> zlib/1.0
        #             \----> boost/1.0 ---------------------> zlib/1.1 (conflict)
        # This conflict is good, the default dependencies are incompatible in definition
        tc = TestClient(light=True)
        pkg = GenConanfile("pkg1", "1.0")
        if order:
            pkg.with_requirement("gtest/1.0", visible=False, test=test).with_requirement("boost/1.0")
        else:
            pkg.with_requirement("boost/1.0").with_requirement("gtest/1.0", visible=False, test=test)
        tc.save({"zlib/conanfile.py": GenConanfile("zlib"),
                 "boost/conanfile.py": GenConanfile("boost", "1.0").with_requirement("zlib/1.1"),
                 "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requirement("zlib/1.0"),
                 "pkg1/conanfile.py": pkg})
        tc.run("export zlib --version=1.0")
        tc.run("export zlib --version=1.1")
        tc.run("export boost")
        tc.run("export gtest")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg1/1.0", assert_error=True)
        if order:
            assert "ERROR: Version conflict: Conflict between zlib/1.1 and zlib/1.0" in tc.out
            assert "Conflict originates from boost/1.0" in tc.out
        else:
            assert "ERROR: Version conflict: Conflict between zlib/1.0 and zlib/1.1" in tc.out
            assert "Conflict originates from gtest/1.0" in tc.out

    def test_subgraph_no_conflict(self, order, test):
        #  cli--> pkg1/1.0 -(visible=False) --------------> pkg3/1.0 (no conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.0 (no conflict)
        # This doesn't conflict, but package topology is affected, converging to a direct dependency
        # of a visible one
        #  cli--> pkg1/1.0 -(visible=True) --------------> pkg3/1.0 (no conflict)
        #             \----> pkg2/1.0 ----------------------/
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False, test=test).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False, test=test)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.0"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg2")
        tc.run("export pkg1")

        tc.run("graph info --requires=pkg1/1.0 --format=json")
        if not test:
            assert "WARN: risk: Packages required both with visible=True and visible=False" in tc.out
            assert "pkg3/1.0: Required by pkg1/1.0" in tc.out
        else:
            assert "WARN: risk" not in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 4  # Including the CLI 0-3
        pkg1 = graph["graph"]["nodes"]["1"]
        deps = pkg1["dependencies"]
        assert len(deps) == 2
        assert "pkg1/1.0" in pkg1["ref"]
        if order:
            dep_pkg2 = deps["3"]
            dep_pkg3 = deps["2"]
        else:
            dep_pkg2 = deps["2"]
            dep_pkg3 = deps["3"]
        assert dep_pkg2["ref"] == "pkg2/1.0"
        assert dep_pkg2["visible"] is True
        assert dep_pkg3["ref"] == "pkg3/1.0"
        assert dep_pkg2["visible"] is True

    def test_subgraph_no_conflict_second_level(self, order, test):
        #  cli--> pkg1/1.0 -(visible=False) ---> gtest/1.0 -> zlib/1.0
        #             \----> boost/1.0 ---------------------> zlib/1.0 (noconflict)
        tc = TestClient(light=True)
        pkg = GenConanfile("pkg1", "1.0")
        if order:
            pkg.with_requirement("gtest/1.0", visible=False, test=test).with_requirement("boost/1.0")
        else:
            pkg.with_requirement("boost/1.0").with_requirement("gtest/1.0", visible=False, test=test)
        tc.save({"zlib/conanfile.py": GenConanfile("zlib"),
                 "boost/conanfile.py": GenConanfile("boost", "1.0").with_requirement("zlib/1.0"),
                 "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requirement("zlib/1.0"),
                 "pkg1/conanfile.py": pkg})
        tc.run("export zlib --version=1.0")
        tc.run("export boost")
        tc.run("export gtest")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg1/1.0 --format=json")
        assert "WARN: risk: Packages required both with visible=True and visible=False" not in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 5  # Including the CLI 0-4
        pkg1 = graph["graph"]["nodes"]["1"]
        deps = pkg1["dependencies"]
        assert len(deps) == 3
        zlib = deps["3"]
        assert "zlib/1.0" in zlib["ref"]
        assert zlib["visible"] is True

    def test_transitive_conflict(self, order, test):
        # cli --------------------------------------------> pkg3/1.1
        #   \--> pkg1/1.0 -(visible=False) -> pkg3/1.0 (conflict)
        #             \----> pkg2/1.0 --------------------> pkg3/1.1 (no conflict)
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/1.0", visible=False, test=test).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/1.0", visible=False, test=test)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0 --format=html", assert_error=True,
               redirect_stdout="graph.html")
        # Check that the graph.html is generated
        assert os.path.exists(os.path.join(tc.current_folder, "graph.html"))
        if order:
            assert "ERROR: Version conflict: Conflict between pkg3/1.1 and pkg3/1.0" in tc.out
        else:
            assert "ERROR: Version conflict: Conflict between pkg3/1.0 and pkg3/1.1" in tc.out
        assert "Conflict originates from pkg1/1.0" in tc.out

    def test_transitive_conflict_second_level(self, order, test):
        # cli --------------------------------------------> zlib/1.1
        #   \--> pkg1/1.0 -(visible=False) -gtest---------> zlib/1.0 (conflict)
        #             \----> boost/1.0 -------------------> zlib/1.1 (no conflict)
        tc = TestClient(light=True)
        pkg = GenConanfile("pkg1", "1.0")
        if order:
            pkg.with_requirement("gtest/1.0", visible=False, test=test).with_requirement("boost/1.0")
        else:
            pkg.with_requirement("boost/1.0").with_requirement("gtest/1.0", visible=False, test=test)
        tc.save({"zlib/conanfile.py": GenConanfile("zlib"),
                 "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requirement("zlib/1.0"),
                 "boost/conanfile.py": GenConanfile("boost", "1.0").with_requirement("zlib/1.1"),
                 "pkg1/conanfile.py": pkg})
        tc.run("export zlib --version=1.0")
        tc.run("export zlib --version=1.1")
        tc.run("export gtest")
        tc.run("export boost")
        tc.run("export pkg1")
        tc.run("graph info --requires=zlib/1.1 --requires=pkg1/1.0 --format=html", assert_error=True,
               redirect_stdout="graph.html")
        # Check that the graph.html is generated
        assert os.path.exists(os.path.join(tc.current_folder, "graph.html"))
        if order:
            assert "ERROR: Version conflict: Conflict between zlib/1.1 and zlib/1.0" in tc.out
            assert "Conflict originates from pkg1/1.0" in tc.out
        else:
            assert "ERROR: Version conflict: Conflict between zlib/1.0 and zlib/1.1" in tc.out
            assert "Conflict originates from gtest/1.0" in tc.out

    def test_transitive_version_range_no_conflict(self, order, test):
        # if in the case above, we use a version-range, we can avoid the conflict
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/[*]", visible=False, test=test).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/[*]", visible=False, test=test)
        tc.save({"pkg3/conanfile.py": GenConanfile("pkg3"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")
        tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0 --format=json")
        if not test:
            assert "WARN: risk: Packages required both with visible=True and visible=False" in tc.out
            assert "pkg3/1.1: Required by pkg1/1.0" in tc.out
        else:
            assert "WARN: risk" not in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 4  # This was having an orphan node!!!
        pkg1 = graph["graph"]["nodes"]["2"]
        deps = pkg1["dependencies"]
        assert len(deps) == 2
        assert "pkg1/1.0" in pkg1["ref"]
        dep_pkg2 = deps["3"]
        dep_pkg3 = deps["1"]
        assert dep_pkg2["ref"] == "pkg2/1.0"
        assert dep_pkg2["visible"] is True
        assert dep_pkg3["ref"] == "pkg3/1.1"
        assert dep_pkg2["visible"] is True

    def test_transitive_version_range_no_conflict_second_level(self, order, test):
        # cli --------------------------------------------> zlib/1.1
        #   \--> pkg1/1.0 -(visible=False) -gtest---------> zlib/[*] (no conflict, range)
        #             \----> boost/1.0 -------------------> zlib/1.1 (no conflict)
        tc = TestClient(light=True)
        pkg = GenConanfile("pkg1", "1.0")
        if order:
            pkg.with_requirement("gtest/1.0", visible=False, test=test).with_requirement("boost/1.0")
        else:
            pkg.with_requirement("boost/1.0").with_requirement("gtest/1.0", visible=False, test=test)
        tc.save({"zlib/conanfile.py": GenConanfile("zlib"),
                 "gtest/conanfile.py": GenConanfile("gtest", "1.0").with_requirement("zlib/[*]"),
                 "boost/conanfile.py": GenConanfile("boost", "1.0").with_requirement("zlib/1.1"),
                 "pkg1/conanfile.py": pkg})
        tc.run("export zlib --version=1.0")
        tc.run("export zlib --version=1.1")
        tc.run("export gtest")
        tc.run("export boost")
        tc.run("export pkg1")
        tc.run("graph info --requires=zlib/1.1 --requires=pkg1/1.0 --build=missing")
        assert "pkg1/1.0: WARN: risk: This package has 2 different dependencies" not in tc.out
        # This doesn't conflict, but depending on the order, it is possible to have 2 differnet
        # dependency graphs. If gtest is evaluated first, there will be no diamond, and
        # gtest->zlib/1.1 will be private, and there will be another branch with another zlib/1.1
        # node as regular requires.
        # In both cases, it seems that zlib is not Skipped when it is necessary to build gtest

    def test_transitive_orphans(self, order, test):
        tc = TestClient(light=True)
        pkg1 = GenConanfile("pkg1", "1.0")
        if order:
            pkg1.with_requirement("pkg3/[*]", visible=False, test=test).with_requirement("pkg2/1.0")
        else:
            pkg1.with_requirement("pkg2/1.0").with_requirement("pkg3/[*]", visible=False, test=test)
        tc.save({"pkg4/conanfile.py": GenConanfile("pkg4", "0.1"),
                 "pkg3/conanfile.py": GenConanfile("pkg3").with_requires("pkg4/0.1"),
                 "pkg2/conanfile.py": GenConanfile("pkg2", "1.0").with_requirement("pkg3/1.1"),
                 "pkg1/conanfile.py": pkg1})
        tc.run("export pkg4")
        tc.run("export pkg3 --version=1.0")
        tc.run("export pkg3 --version=1.1")
        tc.run("export pkg2")
        # Creating this pkg1 does generate a conflict
        tc.run("export pkg1")

        tc.run("graph info --requires=pkg3/1.1 --requires=pkg1/1.0 --format=json")
        if not test:
            assert "WARN: risk: Packages required both with visible=True and visible=False" in tc.out
            assert "pkg3/1.1: Required by pkg1/1.0" in tc.out
        else:
            assert "WARN: risk" not in tc.out
        graph = json.loads(tc.stdout)
        assert len(graph["graph"]["nodes"]) == 5  # This was having an orphan node!!!
        pkg1 = graph["graph"]["nodes"]["3"]
        assert "pkg1/1.0" in pkg1["ref"]
        deps = pkg1["dependencies"]
        assert len(deps) == 3
        dep_pkg2 = deps["4"]
        dep_pkg3 = deps["1"]
        assert dep_pkg2["ref"] == "pkg2/1.0"
        assert dep_pkg2["visible"] is True
        assert dep_pkg3["ref"] == "pkg3/1.1"
        assert dep_pkg2["visible"] is True
