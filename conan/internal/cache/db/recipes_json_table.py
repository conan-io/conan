"""
JSON file-based implementation of the recipes cache table.
Replaces SQLite for recipes to allow a distributed/shared Conan cache.

Lock-free, designed for shared folders with eventual consistency:
- Folder existence is the indicator of existence; data.json is read with retry on failure.
- Writes use atomic replace (write to .tmp then rename).
- Updates are rare; concurrent reads dominate. Occasional read-during-write is handled by retry.
"""

import os
import shutil
from typing import List

from conan.api.model import RecipeReference
from conan.internal.cache.db.json_db import ref_hash, write_json_atomic, read_json_with_retry
from conan.internal.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB


class RecipesJsonTable:
    """
    Lock-free, concurrent-safe recipes table for shared folders (eventual consistency).
    Same public API as RecipesDBTable; uses folder existence + retry on data.json.

    <db_folder>/<ref_hash>/data.json {"ref": ...}
    <db_folder>/<ref_hash>/<rrev>/data.json {"timestamp": ..., "path": "..."}
    <db_folder>/<ref_hash>/<rrev>/<pkgid>/<prev>/data.json {"timestamp": ..., "path": "...",
                                                            "build_id": "..."}
    """

    def __init__(self, db_folder: str):
        self._db_folder = os.path.abspath(db_folder)
        os.makedirs(self._db_folder, exist_ok=True)

    def create_table(self):
        """No-op for API compatibility; folder is created in __init__."""
        os.makedirs(self._db_folder, exist_ok=True)

    def _ref_dir(self, ref: RecipeReference) -> str:
        return os.path.join(self._db_folder, ref_hash(str(ref)))

    def _revision_dir(self, ref: RecipeReference) -> str:
        # The revision string itself is a safe hex value — use it directly as folder name.
        return os.path.join(self._ref_dir(ref), ref.revision or "")

    def _ref_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._ref_dir(ref), "data.json")

    def _revision_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._revision_dir(ref), "data.json")

    def create(self, path: str, ref: RecipeReference):
        assert ref is not None
        assert ref.revision is not None
        assert ref.timestamp is not None

        rev_dir = self._revision_dir(ref)

        if os.path.isdir(rev_dir):
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(ref)}' already exists")

        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            os.makedirs(ref_dir, exist_ok=True)
            write_json_atomic(self._ref_data_path(ref), {"ref": str(ref)})

        os.makedirs(rev_dir, exist_ok=True)
        # The revision is the folder name — no need to store it in the file too.
        write_json_atomic(self._revision_data_path(ref), {
            "timestamp": ref.timestamp,
            "path": path,
        })

    def update_timestamp(self, ref: RecipeReference):
        assert ref.revision is not None
        assert ref.timestamp is not None

        rev_dir = self._revision_dir(ref)
        if not os.path.isdir(rev_dir):
            return
        rev_data_path = self._revision_data_path(ref)
        data = read_json_with_retry(rev_data_path)
        data["timestamp"] = ref.timestamp
        write_json_atomic(rev_data_path, data)

    def remove(self, ref: RecipeReference):
        rev_dir = self._revision_dir(ref)
        if os.path.isdir(rev_dir):
            try:
                shutil.rmtree(rev_dir)
            except OSError:
                pass
        ref_dir = self._ref_dir(ref)
        if os.path.isdir(ref_dir):
            try:
                remaining = os.listdir(ref_dir)
                if remaining == ["data.json"]:
                    os.remove(os.path.join(ref_dir, "data.json"))
                    os.rmdir(ref_dir)
            except OSError:
                pass

    def all_references(self) -> List[RecipeReference]:
        refs = set()
        for entry in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, entry)
            if not os.path.isdir(ref_dir):
                continue
            data = read_json_with_retry(os.path.join(ref_dir, "data.json"))
            refs.add(data["ref"])
        return [RecipeReference.loads(r) for r in refs]

    def get_recipe(self, ref: RecipeReference) -> dict:
        rev_dir = self._revision_dir(ref)
        if not os.path.isdir(rev_dir):
            raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref.repr_notime()}' not found")

        rev_data = read_json_with_retry(self._revision_data_path(ref))
        result = ref.copy()
        # revision is the folder name — already set on ref; just carry timestamp forward.
        result.timestamp = rev_data["timestamp"]
        return {
            "ref": result,
            "path": rev_data["path"]
        }

    def get_latest_recipe(self, ref: RecipeReference) -> dict:
        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")

        best_name = None
        best_ts = None
        best_path = None
        for name in os.listdir(ref_dir):
            if name == "data.json":
                continue
            rev_dir = os.path.join(ref_dir, name)
            if not os.path.isdir(rev_dir):
                continue
            rev_data = read_json_with_retry(os.path.join(rev_dir, "data.json"))
            ts = rev_data["timestamp"]
            if best_ts is None or ts > best_ts:
                best_ts = ts
                best_name = name
                best_path = rev_data["path"]

        if best_name is None:
            raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")

        result = ref.copy()
        result.revision = best_name   # folder name IS the revision
        result.timestamp = best_ts
        return {
            "ref": result,
            "path": best_path
        }

    def get_recipe_revisions_references(self, ref: RecipeReference) -> List[RecipeReference]:
        assert ref.revision is None
        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            return []
        if not read_json_with_retry(self._ref_data_path(ref)):
            return []

        revs = []
        for name in os.listdir(ref_dir):
            if name == "data.json":
                continue
            rev_data_path = os.path.join(ref_dir, name, "data.json")
            rev_data = read_json_with_retry(rev_data_path)
            if rev_data is None:
                continue
            revs.append((rev_data["timestamp"], name))  # name IS the revision string

        revs.sort(key=lambda x: x[0], reverse=True)
        result = []
        for ts, rrev in revs:
            r = ref.copy()
            r.revision = rrev
            r.timestamp = ts
            result.append(r)
        return result

    def path_to_ref(self, path: str) -> RecipeReference | None:
        if not os.path.isdir(self._db_folder):
            return None
        for entry in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, entry)
            if not os.path.isdir(ref_dir):
                continue
            ref_data = read_json_with_retry(os.path.join(ref_dir, "data.json"))
            if ref_data is None:
                continue
            for name in os.listdir(ref_dir):
                if name == "data.json":
                    continue
                rev_dir = os.path.join(ref_dir, name)
                if not os.path.isdir(rev_dir):
                    continue
                rev_data = read_json_with_retry(os.path.join(rev_dir, "data.json"))
                if rev_data is None:
                    continue
                if rev_data.get("path") == path:
                    ref = RecipeReference.loads(ref_data["ref"])
                    ref.revision = name   # folder name IS the revision
                    ref.timestamp = rev_data["timestamp"]
                    return ref
        return None
