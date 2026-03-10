import os
import time

import pytest

from conan.api.model import RecipeReference
from conan.internal.cache.db.recipes_json_table import RecipesJsonTable
from conan.test.utils.test_files import temp_folder


@pytest.mark.skip(reason="This is a performance test, skip for normal runs")
def test_recipes_json_table_all_references_performance():
    """Benchmark all_references() over a large RecipesJsonTable (1000 references).
        Creating 1000 recipe references...
      Creation time: 2.215s (2.21 ms/ref)
    Timing all_references() x10...
      Total: 1.146s  Avg per call: 0.115s (114.59 ms)
    """
    tmp = temp_folder()
    db_folder = os.path.join(tmp, "db")
    table = RecipesJsonTable(db_folder)

    num_refs = 1000
    print(f"Creating {num_refs} recipe references...")
    t0 = time.perf_counter()
    for i in range(num_refs):
        ref = RecipeReference.loads(f"pkg/1.{i}@user/channel")
        ref.revision = f"rev{i}"
        ref.timestamp = 1000.0 + i
        path = f"pkgname/hash{i}"
        table.create(path, ref)
    create_time = time.perf_counter() - t0
    print(f"  Creation time: {create_time:.3f}s ({create_time / num_refs * 1000:.2f} ms/ref)")

    experiments = 10
    print(f"Timing all_references() x{experiments}...")
    t0 = time.perf_counter()
    for _ in range(experiments):
        refs = table.all_references()
        assert len(refs) == num_refs
    total_time = time.perf_counter() - t0
    avg_time = total_time / experiments
    print(f"  Total: {total_time:.3f}s  Avg per call: {avg_time:.3f}s ({avg_time * 1000:.2f} ms)")
