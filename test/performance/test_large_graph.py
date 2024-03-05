import cProfile
from test.utils.test_files import temp_folder
import pstats
import time
from pstats import SortKey

from test.assets.genconanfile import GenConanfile
from test.utils.tools import TestClient


def test_large_graph():
    tmp = temp_folder()
    c = TestClient(cache_folder=tmp)
    num_test = 4
    num_pkgs = 4

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
