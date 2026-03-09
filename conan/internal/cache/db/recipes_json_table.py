"""
JSON file-based implementation of the recipes cache table.
Replaces SQLite for recipes to allow a distributed/shared Conan cache.
Structure on disk:
  db/<ref_hash>/
    data.json          -> {"ref": "name/version@user/channel"}
    <rrev>/
      data.json        -> {"revision": "...", "timestamp": float, "path": "..."}
"""

import hashlib
import json
import os
import threading
from collections import defaultdict
from typing import List

from conan.api.model import RecipeReference
from conan.internal.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB


def _ref_hash(ref_str: str) -> str:
    """Path-safe hash for reference (name/version@user/channel). Matches cache path style."""
    h = hashlib.sha256(ref_str.encode("utf-8")).hexdigest()
    return h[:13]


class RecipesJsonTable:
    """
    Drop-in replacement for RecipesDBTable using JSON files on disk.
    Same public API so it can be used transparently via CacheDatabase.
    """

    _lock_storage = defaultdict(threading.Lock)

    def __init__(self, db_folder: str):
        self._db_folder = os.path.abspath(db_folder)
        os.makedirs(self._db_folder, exist_ok=True)
        self._lock = self._lock_storage[self._db_folder]

    def _ref_dir(self, ref: RecipeReference) -> str:
        ref_str = str(ref)
        return os.path.join(self._db_folder, _ref_hash(ref_str))

    def _revision_dir(self, ref: RecipeReference) -> str:
        return os.path.join(self._ref_dir(ref), _ref_hash(ref.revision or ""))

    def _ref_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._ref_dir(ref), "data.json")

    def _revision_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._revision_dir(ref), "data.json")

    def _acquire(self):
        self._lock.acquire()

    def _release(self):
        self._lock.release()

    def create(self, path: str, ref: RecipeReference):
        assert ref is not None
        assert ref.revision is not None
        assert ref.timestamp is not None

        self._acquire()
        try:
            ref_dir = self._ref_dir(ref)
            ref_data_path = os.path.join(ref_dir, "data.json")
            rev_dir = self._revision_dir(ref)
            rev_data_path = self._revision_data_path(ref)

            if os.path.isfile(rev_data_path):
                raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(ref)}' already exists")

            os.makedirs(ref_dir, exist_ok=True)
            if not os.path.isfile(ref_data_path):
                with open(ref_data_path, "w", encoding="utf-8") as f:
                    json.dump({"ref": str(ref)}, f)

            os.makedirs(rev_dir, exist_ok=True)
            with open(rev_data_path, "w", encoding="utf-8") as f:
                json.dump({
                    "revision": ref.revision,
                    "timestamp": ref.timestamp,
                    "path": path,
                }, f)
        finally:
            self._release()

    def update_timestamp(self, ref: RecipeReference):
        assert ref.revision is not None
        assert ref.timestamp is not None

        self._acquire()
        try:
            rev_data_path = self._revision_data_path(ref)
            if not os.path.isfile(rev_data_path):
                return
            with open(rev_data_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["timestamp"] = ref.timestamp
            with open(rev_data_path, "w", encoding="utf-8") as f:
                json.dump(data, f)
        finally:
            self._release()

    def remove(self, ref: RecipeReference):
        self._acquire()
        try:
            rev_dir = self._revision_dir(ref)
            rev_data_path = self._revision_data_path(ref)
            if os.path.isfile(rev_data_path):
                os.remove(rev_data_path)
            if os.path.isdir(rev_dir):
                try:
                    os.rmdir(rev_dir)
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
        finally:
            self._release()

    def all_references(self) -> List[RecipeReference]:
        self._acquire()
        try:
            refs = set()
            for ref_hash_dir in os.listdir(self._db_folder):
                ref_dir = os.path.join(self._db_folder, ref_hash_dir)
                if not os.path.isdir(ref_dir):
                    continue
                data_path = os.path.join(ref_dir, "data.json")
                if not os.path.isfile(data_path):
                    continue
                with open(data_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                refs.add(data["ref"])
            return [RecipeReference.loads(r) for r in refs]
        finally:
            self._release()

    def get_recipe(self, ref: RecipeReference) -> dict:
        rev_data_path = self._revision_data_path(ref)
        self._acquire()
        try:
            if not os.path.isfile(rev_data_path):
                raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref.repr_notime()}' not found")
            with open(rev_data_path, "r", encoding="utf-8") as f:
                rev_data = json.load(f)
            result = ref.copy()
            result.revision = rev_data["revision"]
            result.timestamp = rev_data["timestamp"]
            return {
                "ref": result,
                "path": rev_data["path"]
            }
        finally:
            self._release()

    def get_latest_recipe(self, ref: RecipeReference) -> dict:
        ref_dir = self._ref_dir(ref)
        self._acquire()
        try:
            if not os.path.isdir(ref_dir):
                raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")
            ref_data_path = self._ref_data_path(ref)
            if not os.path.isfile(ref_data_path):
                raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")

            best = None
            best_ts = None
            for name in os.listdir(ref_dir):
                if name == "data.json":
                    continue
                rev_dir = os.path.join(ref_dir, name)
                rev_data_path = os.path.join(rev_dir, "data.json")
                if not os.path.isfile(rev_data_path):
                    continue
                with open(rev_data_path, "r", encoding="utf-8") as f:
                    rev_data = json.load(f)
                ts = rev_data["timestamp"]
                if best_ts is None or ts > best_ts:
                    best_ts = ts
                    best = rev_data

            if best is None:
                raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")

            result = ref.copy()
            result.revision = best["revision"]
            result.timestamp = best["timestamp"]
            return {
                "ref": result,
                "path": best["path"]
            }
        finally:
            self._release()

    def get_recipe_revisions_references(self, ref: RecipeReference) -> List[RecipeReference]:
        assert ref.revision is None
        ref_dir = self._ref_dir(ref)
        self._acquire()
        try:
            if not os.path.isdir(ref_dir):
                return []
            ref_data_path = self._ref_data_path(ref)
            if not os.path.isfile(ref_data_path):
                return []

            revs = []
            for name in os.listdir(ref_dir):
                if name == "data.json":
                    continue
                rev_data_path = os.path.join(ref_dir, name, "data.json")
                if not os.path.isfile(rev_data_path):
                    continue
                with open(rev_data_path, "r", encoding="utf-8") as f:
                    rev_data = json.load(f)
                revs.append((rev_data["timestamp"], rev_data["revision"]))

            revs.sort(key=lambda x: x[0], reverse=True)
            result = []
            for ts, rrev in revs:
                r = ref.copy()
                r.revision = rrev
                r.timestamp = ts
                result.append(r)
            return result
        finally:
            self._release()

    def path_to_ref(self, path: str) -> RecipeReference | None:
        self._acquire()
        try:
            if not os.path.isdir(self._db_folder):
                return None
            for ref_hash_dir in os.listdir(self._db_folder):
                ref_dir = os.path.join(self._db_folder, ref_hash_dir)
                if not os.path.isdir(ref_dir):
                    continue
                ref_data_path = os.path.join(ref_dir, "data.json")
                if not os.path.isfile(ref_data_path):
                    continue
                with open(ref_data_path, "r", encoding="utf-8") as f:
                    ref_data = json.load(f)
                reference = ref_data["ref"]
                for name in os.listdir(ref_dir):
                    if name == "data.json":
                        continue
                    rev_data_path = os.path.join(ref_dir, name, "data.json")
                    if not os.path.isfile(rev_data_path):
                        continue
                    with open(rev_data_path, "r", encoding="utf-8") as f:
                        rev_data = json.load(f)
                    if rev_data.get("path") == path:
                        ref = RecipeReference.loads(reference)
                        ref.revision = rev_data["revision"]
                        ref.timestamp = rev_data["timestamp"]
                        return ref
            return None
        finally:
            self._release()
