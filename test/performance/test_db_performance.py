import os
import time

import pytest

from conan.api.model import RecipeReference
from conan.internal.cache.db.cache_database import CacheDatabase
from conan.test.utils.test_files import temp_folder


@pytest.mark.skip(reason="This is a performance test, skip for normal runs")
def test_db_performance():
    f = temp_folder()
    # f = r"C:\conan_tests\tmp_o0846cmconans\path with spaces"
    print("Tempt folder: ", f)
    db = CacheDatabase(os.path.join(f, "mytest.sqlite"))

    num_refs = 1000
    splits = 10
    for num_split in range(10):
        init = time.time()
        for i in range(int(num_refs / splits)):
            index = num_split * int(num_refs / splits) + i
            ref = RecipeReference.loads(f"pkg/1.{index}#rev1%1")
            path = os.path.join(f, f"folder{index}")
            db.create_recipe(path, ref)
        creation_time = time.time() - init
        print(f"Creation time {num_split}:", creation_time)
        print("    Avg:", creation_time/num_refs)

    experiments = 10
    texp = time.time()
    for experiment in range(experiments):
        ret = db.list_references()
        assert len(ret) == num_refs
    exp_time = time.time() - texp
    print("SEARCH RECIPES time:", exp_time)
    print("    Avg:", exp_time / experiments)

    texp = time.time()
    specific_ref = RecipeReference.loads(f"pkg/1.1#rev1%1")
    for experiment in range(experiments):
        db.get_recipe(specific_ref)
    exp_time = time.time() - texp
    print("GET RECIPE time:", exp_time)
    print("    Avg:", exp_time / experiments)

    texp = time.time()
    specific_ref = RecipeReference.loads(f"pkg/1.1#rev1%1")
    for experiment in range(experiments):
        db.get_latest_recipe(specific_ref)
    exp_time = time.time() - texp
    print("GET LATEST RECIPE time:", exp_time)
    print("    Avg:", exp_time / experiments)

    texp = time.time()
    for experiment in range(experiments):
        db.update_recipes_lru([specific_ref])
    exp_time = time.time() - texp
    print("UPDATE LRU:", exp_time)
    print("    Avg:", exp_time / experiments)

    updates = 50
    texp = time.time()
    for experiment in range(experiments):
        refs = [RecipeReference.loads(f"pkg/1.{index}#rev1%1") for index in range(updates)]
        db.update_recipes_lru(refs)
    exp_time = time.time() - texp
    print("UPDATE LRU BATCH:", exp_time)
    print("    Avg:", exp_time / experiments)
    print("    Avg:", exp_time / (experiments * updates))



