import cProfile
import json
import pstats
import time
from pstats import SortKey

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def test_large_graph():
    c = TestClient(cache_folder="T:/mycache")
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
