"""
Concurrency stress tests for RecipesJsonTable (lock-free, shared folder, eventual consistency).
Multiple readers and writers use the same db folder; we assert no crashes and eventual consistency.
"""

import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest

from conan.api.model import RecipeReference
from conan.internal.cache.db.recipes_json_table import RecipesJsonTable
from conan.test.utils.test_files import temp_folder


def _make_ref(i: int, rev_suffix: str = "0") -> RecipeReference:
    ref = RecipeReference.loads(f"pkg/1.{i}@user/channel")
    ref.revision = f"rev{rev_suffix}"
    ref.timestamp = 1000.0 + i
    return ref


@pytest.mark.skip(reason="Concurrency stress test, skip for normal runs")
def test_recipes_json_table_concurrent_readers_writers():
    """Many threads read (all_references, get_recipe, get_latest_recipe) while a few create/update."""
    tmp = temp_folder()
    db_folder = os.path.join(tmp, "db")
    table = RecipesJsonTable(db_folder)
    table.create_table()

    # Pre-populate a base set so readers have something to read
    num_pre = 50
    for i in range(num_pre):
        ref = _make_ref(i)
        table.create(f"path{i}", ref)

    errors = []
    num_readers = 20
    num_writers = 4
    rounds = 30

    def reader(_tid: int):
        try:
            for _ in range(rounds):
                refs = table.all_references()
                assert len(refs) >= num_pre
                if refs:
                    r = refs[0]
                    data = table.get_recipe(_make_ref(0))
                    assert data["ref"].revision
                    data2 = table.get_latest_recipe(RecipeReference.loads("pkg/1.0@user/channel"))
                    assert data2["path"]
        except Exception as e:
            errors.append(("reader", _tid, e))

    def writer(_tid: int):
        try:
            for i in range(rounds):
                # Create new refs in a range that doesn't overlap other writers
                base = 1000 * _tid + i
                ref = _make_ref(base, rev_suffix=str(i))
                try:
                    table.create(f"path_{base}", ref)
                except Exception:
                    pass  # already exists is ok
                # Update timestamp on an existing ref occasionally
                if i % 5 == 0 and num_pre > 0:
                    ref0 = _make_ref(0)
                    ref0.timestamp = 2000.0 + i
                    table.update_timestamp(ref0)
        except Exception as e:
            errors.append(("writer", _tid, e))

    with ThreadPoolExecutor(max_workers=num_readers + num_writers) as ex:
        futs = [ex.submit(reader, i) for i in range(num_readers)]
        futs += [ex.submit(writer, i) for i in range(num_writers)]
        for f in as_completed(futs):
            f.result()

    assert not errors, errors


@pytest.mark.skip(reason="Concurrency stress test, skip for normal runs")
def test_recipes_json_table_concurrent_all_references_stress():
    """Many threads call all_references() repeatedly while others create refs."""
    tmp = temp_folder()
    db_folder = os.path.join(tmp, "db")
    table = RecipesJsonTable(db_folder)
    table.create_table()

    for i in range(20):
        ref = _make_ref(i)
        table.create(f"path{i}", ref)

    count_per_thread = 100
    num_reader_threads = 15
    num_writer_threads = 3
    stop_writers = threading.Event()

    def read_loop():
        for _ in range(count_per_thread):
            refs = table.all_references()
            assert len(refs) >= 20

    def write_loop():
        j = 0
        while not stop_writers.is_set():
            ref = _make_ref(500 + j % 10, rev_suffix=str(j))
            try:
                table.create(f"path_w{j}", ref)
            except Exception:
                pass
            j += 1

    with ThreadPoolExecutor(max_workers=num_reader_threads + num_writer_threads) as ex:
        writers = [ex.submit(write_loop) for _ in range(num_writer_threads)]
        readers = [ex.submit(read_loop) for _ in range(num_reader_threads)]
        for f in as_completed(readers):
            f.result()
        stop_writers.set()
        for f in writers:
            f.result(timeout=2)

    refs = table.all_references()
    assert len(refs) >= 20


def test_recipes_json_table_retry_on_incomplete_file():
    """
    Simulate another process writing data.json: we create the folder and an incomplete
    data.json, then complete it. A reader should eventually see the complete data (retry).
    """
    from conan.internal.cache.db.recipes_json_table import _ref_hash

    tmp = temp_folder()
    db_folder = os.path.join(tmp, "db")
    table = RecipesJsonTable(db_folder)
    table.create_table()

    ref = _make_ref(0)
    ref_dir = os.path.join(db_folder, _ref_hash(str(ref)))
    rev_dir = os.path.join(ref_dir, _ref_hash(ref.revision or ""))
    rev_data_path = os.path.join(rev_dir, "data.json")
    ref_data_path = os.path.join(ref_dir, "data.json")

    os.makedirs(ref_dir, exist_ok=True)
    with open(ref_data_path, "w", encoding="utf-8") as f:
        f.write('{"ref": "pkg/1.0@user/channel"}')

    # Create revision dir and write incomplete JSON (reader will retry)
    os.makedirs(rev_dir, exist_ok=True)
    with open(rev_data_path, "w", encoding="utf-8") as f:
        f.write('{"revision": "incomplete')  # invalid JSON

    # Reader should fail first time (incomplete); we then complete the file
    def complete_after_delay():
        time.sleep(0.05)
        with open(rev_data_path, "w", encoding="utf-8") as f:
            f.write('{"revision": "rev0", "timestamp": 1000.0, "path": "path0"}')

    t = threading.Thread(target=complete_after_delay)
    t.start()
    try:
        data = table.get_recipe(ref)
        assert data["ref"].revision == "rev0"
        assert data["path"] == "path0"
    finally:
        t.join()
