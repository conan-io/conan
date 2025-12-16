import os
import time
from unittest.mock import patch

import pytest

from conan.api.model import RecipeReference
from conan.internal.cache.db.cache_database import CacheDatabase
from conan.internal.cache.db.packages_table import PackagesDBTable
from conan.internal.cache.db.recipes_table import RecipesDBTable
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


def test_contexts():
    from contextlib import contextmanager

    class MyConnection:
        def __init__(self):
            print("Constructing MYConnection")

        def __enter__(self):
            print("Enter MYConnection")

        def close(self):
            print("Close MYConnection")

        def do_something(self):
            print("Do something MYConnection")

        def __exit__(self, type, value, traceback):
            print("Exit MYConnection")

    @contextmanager
    def mydb_connection():
        connection = MyConnection()
        try:
            yield connection
        finally:
            connection.close()

    with mydb_connection() as conn:
        conn.do_something()


def test_db_traces():
    f = temp_folder()
    print("Tempt folder: ", f)
    db = CacheDatabase(os.path.join(f, "mytest.sqlite"))

    index = 0
    ref = RecipeReference.loads(f"pkg/1.{index}#rev1%1")
    path = os.path.join(f, f"folder{index}")
    db.create_recipe(path, ref)


def test_pure_db_traces():
    import sqlite3
    f = temp_folder()
    filename = os.path.join(f, "mytest.sqlite")

    try:
        with sqlite3.connect(filename, isolation_level=None) as connection:
            connection.set_trace_callback(print)
            connection.execute("CREATE TABLE users (id INTEGER, name TEXT)")
            connection.execute("INSERT INTO users VALUES (1, 'John Doe')")
            connection.execute("INSERT INTO users VALUES (2, 'Jane Doe')")
            connection.execute("INSERT INTO users VALUESS (3, 'John Smith')")
    except sqlite3.OperationalError as e:
        print(e)

    r = connection.execute("SELECT * FROM users")
    print("IN TRANSACTION", connection.in_transaction)
    ret = len(r.fetchall())
    assert ret == 2

    connection.close()

    f = temp_folder()
    filename = os.path.join(f, "mytest2.sqlite")
    ptable = PackagesDBTable(filename)
    rtable = RecipesDBTable(filename)
    assert ptable._lock is rtable._lock
    print(id(ptable._lock), id(rtable._lock))
