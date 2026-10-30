import cProfile
import os
import pstats
import time
from pstats import SortKey
import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def _conanfile(name, with_settings):
    conanfile = GenConanfile(name, "0.1")
    if with_settings:
        # A typical recipe, every node of the graph copies the settings and options several times
        conanfile.with_package_type("library")
        conanfile.with_settings("os", "arch", "compiler", "build_type")
        conanfile.with_option("shared", [True, False]).with_option("fPIC", [True, False])
        conanfile.with_default_option("shared", False).with_default_option("fPIC", True)
    return conanfile


@pytest.mark.skip(reason="This is a performance test, skip for normal runs")
def test_large_graph():
    c = TestClient(cache_folder=os.path.join(os.path.dirname(__file__), "cache"))
    num_test = 40
    num_pkgs = 40

    """for i in range(num_test):
        conanfile = GenConanfile(f"test{i}", "0.1")
        if i > 0:
            conanfile.with_requires(f"test{i-1}/0.1")
        c.save({"conanfile.py": conanfile})
        c.run("create .")

    for i in range(num_pkgs):
        conanfile = GenConanfile(f"pkg{i}", "0.1").with_test_requires(f"test{num_test-1}/0.1")
        if i > 0:
            conanfile.with_requires(f"pkg{i-1}/0.1")
        c.save({"conanfile.py": conanfile})
        c.run("create .")

    """
    t = time.time()
    pr = cProfile.Profile()
    pr.enable()
    c.run(f"install --requires=pkg{num_pkgs - 1}/0.1")
    pr.disable()
    print(time.time()-t)

    sortby = SortKey.CUMULATIVE
    ps = pstats.Stats(pr).sort_stats(sortby)
    ps.print_stats()

    #graph = json.loads(c.stdout)
    #assert len(graph["graph"]["nodes"]) == 1 + num_pkgs + num_test * num_pkgs


@pytest.mark.skip(reason="This is a performance test, skip for normal runs")
@pytest.mark.parametrize("with_settings", [False, True], ids=["no_settings", "settings"])
def test_large_graph2(with_settings):
    # Different cache folders, the recipes are exported again with different content
    cache_folder = "cache_settings" if with_settings else "cache"
    c = TestClient(cache_folder=os.path.join(os.path.dirname(__file__), cache_folder))
    num_test = 20
    num_pkgs = 20
    branches = ["a", "b", "c"]

    c.save({"conanfile.py": _conanfile("testbase", with_settings)})
    c.run("export .")
    for i in range(num_test):
        for branch in branches:
            conanfile = _conanfile(f"test{branch}{i}", with_settings)
            if i > 0:
                conanfile.with_requires(f"test{branch}{i-1}/0.1", "testbase/0.1")
            else:
                conanfile.with_requires("testbase/0.1")
            c.save({"conanfile.py": conanfile})
            c.run("export .")

    for i in range(num_pkgs):
        conanfile = _conanfile(f"pkg{i}", with_settings)
        for branch in branches:
            conanfile.with_test_requires(f"test{branch}{num_test-1}/0.1")
        if i > 0:
            conanfile.with_requires(f"pkg{i-1}/0.1")
        c.save({"conanfile.py": conanfile})
        c.run("export .")

    t = time.time()
    pr = cProfile.Profile()
    pr.enable()
    c.run(f"graph info --requires=pkg{num_pkgs - 1}/0.1")
    pr.disable()
    print(time.time()-t)

    sortby = SortKey.CUMULATIVE
    ps = pstats.Stats(pr).sort_stats(sortby)
    ps.print_stats()
