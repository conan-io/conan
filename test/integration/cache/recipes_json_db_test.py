"""
Tests for the JSON file-based recipes cache (RecipesJsonTable).
Verifies that the db folder is created under storage path and that recipe operations work.
"""

import os

import pytest

from conan.test.utils.tools import TestClient, GenConanfile


@pytest.mark.parametrize("storage_path", [None, "custom_storage"], ids=["default", "custom_path"])
def test_recipes_json_db_creates_db_folder(storage_path):
    """Recipe metadata is stored in Conan home under 'db' subfolder."""
    client = TestClient()
    if storage_path:
        client.save_home({"global.conf": "core.cache:storage_path=" + client.cache_folder})
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("create . --name=pkg --version=1.0")

    # Default: store is cache_folder/p → db is cache_folder/p/db
    # Custom storage_path=cache_folder: store is cache_folder → db is cache_folder/db
    if storage_path:
        db_folder = os.path.join(client.cache_folder, "db")
    else:
        db_folder = os.path.join(client.cache_folder, "p", "db")
    assert os.path.isdir(db_folder), f"Expected db folder at {db_folder}"

    # Should have at least one ref hash folder and data.json files
    entries = os.listdir(db_folder)
    assert len(entries) >= 1
    ref_hash_dir = os.path.join(db_folder, entries[0])
    if os.path.isdir(ref_hash_dir):
        ref_data = os.path.join(ref_hash_dir, "data.json")
        assert os.path.isfile(ref_data)
        rev_dirs = [d for d in os.listdir(ref_hash_dir) if d != "data.json"]
        if rev_dirs:
            rev_data = os.path.join(ref_hash_dir, rev_dirs[0], "data.json")
            assert os.path.isfile(rev_data)


def test_recipes_json_db_list_and_get():
    """list and get_recipe work with JSON backend."""
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("create . --name=pkg --version=1.0")
    client.run("list *")
    assert "pkg/1.0" in client.out
    client.run("cache path pkg/1.0")
    assert client.out  # path is printed
