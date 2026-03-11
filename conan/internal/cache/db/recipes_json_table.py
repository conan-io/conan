"""
JSON file-based implementation of the recipes cache table.
Replaces SQLite for recipes to allow a distributed/shared Conan cache.

Lock-free, designed for shared folders with eventual consistency:
- Folder existence is the indicator of existence; data.json is read with retry on failure.
- Writes use atomic replace (write to .tmp then rename).
- Updates are rare; concurrent reads dominate. Occasional read-during-write is handled by retry.
"""

import hashlib
import json
import os
import time
from typing import List

from conan.api.model import RecipeReference
from conan.errors import ConanException
from conan.internal.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB

# Retry when reading data.json and parent dir exists (incomplete write by another process)
_READ_JSON_MAX_RETRIES = 5
_READ_JSON_INITIAL_DELAY_S = 0.01
_READ_JSON_MAX_DELAY_S = 0.5


def _ref_hash(ref_str: str) -> str:
    """Path-safe hash for reference (name/version@user/channel). Matches cache path style."""
    h = hashlib.sha256(ref_str.encode("utf-8")).hexdigest()
    return h[:13]


def _read_json_with_retry(filepath: str) -> dict:
    """
    Read JSON file. If parent_dir is set and exists, retry on failure (incomplete write elsewhere).
    Returns None if file missing or invalid after retries.
    """
    for attempt in range(_READ_JSON_MAX_RETRIES):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            time.sleep(min(
                _READ_JSON_INITIAL_DELAY_S * (2 ** attempt),
                _READ_JSON_MAX_DELAY_S
            ))
    raise ConanException("Concurrency error in RecipesDBJson")


def _write_json_atomic(filepath: str, data: dict) -> None:
    """Write JSON atomically via a .tmp file and replace."""
    tmp = filepath + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, filepath)


class RecipesJsonTable:
    """
    Lock-free, concurrent-safe recipes table for shared folders (eventual consistency).
    Same public API as RecipesDBTable; uses folder existence + retry on data.json.
    """

    def __init__(self, db_folder: str):
        self._db_folder = os.path.abspath(db_folder)
        os.makedirs(self._db_folder, exist_ok=True)

    def create_table(self):
        """No-op for API compatibility; folder is created in __init__."""
        os.makedirs(self._db_folder, exist_ok=True)

    def _ref_dir(self, ref: RecipeReference) -> str:
        ref_str = str(ref)
        return os.path.join(self._db_folder, _ref_hash(ref_str))

    def _revision_dir(self, ref: RecipeReference) -> str:
        return os.path.join(self._ref_dir(ref), _ref_hash(ref.revision or ""))

    def _ref_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._ref_dir(ref), "data.json")

    def _revision_data_path(self, ref: RecipeReference) -> str:
        return os.path.join(self._revision_dir(ref), "data.json")

    def create(self, path: str, ref: RecipeReference):
        assert ref is not None
        assert ref.revision is not None
        assert ref.timestamp is not None

        rev_dir = self._revision_dir(ref)

        # Folder existence = revision exists; retry read to handle concurrent write
        if os.path.isdir(rev_dir):
            # TODO: We might want to handle this mode for concurrent writes of same ref
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(ref)}' already exists")
            # Dir exists but no valid data after retries; overwrite (recover from partial write)

        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            os.makedirs(ref_dir, exist_ok=True)
            ref_data_path = os.path.join(ref_dir, "data.json")
            _write_json_atomic(ref_data_path, {"ref": str(ref)})

        os.makedirs(rev_dir, exist_ok=True)
        rev_data_path = self._revision_data_path(ref)
        _write_json_atomic(rev_data_path, {
            "revision": ref.revision,
            "timestamp": ref.timestamp,
            "path": path,
        })

    def update_timestamp(self, ref: RecipeReference):
        assert ref.revision is not None
        assert ref.timestamp is not None

        rev_dir = self._revision_dir(ref)
        rev_data_path = self._revision_data_path(ref)
        if not os.path.isdir(rev_dir):
            return
        data = _read_json_with_retry(rev_data_path)
        if data is None:
            return
        data["timestamp"] = ref.timestamp
        _write_json_atomic(rev_data_path, data)

    def remove(self, ref: RecipeReference):
        rev_dir = self._revision_dir(ref)
        rev_data_path = self._revision_data_path(ref)
        if os.path.isfile(rev_data_path):
            try:
                os.remove(rev_data_path)
            except OSError:
                pass
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

    def all_references(self) -> List[RecipeReference]:
        refs = set()
        for ref_hash_dir in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, ref_hash_dir)
            if not os.path.isdir(ref_dir):
                continue
            data_path = os.path.join(ref_dir, "data.json")
            data = _read_json_with_retry(data_path)
            refs.add(data["ref"])
        return [RecipeReference.loads(r) for r in refs]

    def get_recipe(self, ref: RecipeReference) -> dict:
        rev_dir = self._revision_dir(ref)
        if not os.path.isdir(rev_dir):
            raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref.repr_notime()}' not found")

        rev_data_path = self._revision_data_path(ref)
        rev_data = _read_json_with_retry(rev_data_path)
        result = ref.copy()
        result.revision = rev_data["revision"]
        result.timestamp = rev_data["timestamp"]
        return {
            "ref": result,
            "path": rev_data["path"]
        }

    def get_latest_recipe(self, ref: RecipeReference) -> dict:
        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            raise ConanReferenceDoesNotExistInDB(f"Recipe '{ref}' not found")

        best = None
        best_ts = None
        for name in os.listdir(ref_dir):
            if name == "data.json":
                continue
            rev_dir = os.path.join(ref_dir, name)
            rev_data_path = os.path.join(rev_dir, "data.json")
            rev_data = _read_json_with_retry(rev_data_path)
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

    def get_recipe_revisions_references(self, ref: RecipeReference) -> List[RecipeReference]:
        assert ref.revision is None
        ref_dir = self._ref_dir(ref)
        if not os.path.isdir(ref_dir):
            return []
        ref_data = _read_json_with_retry(self._ref_data_path(ref),)
        if ref_data is None:
            return []

        revs = []
        for name in os.listdir(ref_dir):
            if name == "data.json":
                continue
            rev_data_path = os.path.join(ref_dir, name, "data.json")
            rev_data = _read_json_with_retry(rev_data_path)
            if rev_data is None:
                continue
            revs.append((rev_data["timestamp"], rev_data["revision"]))

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
        for ref_hash_dir in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, ref_hash_dir)
            if not os.path.isdir(ref_dir):
                continue
            ref_data = _read_json_with_retry(os.path.join(ref_dir, "data.json"))
            if ref_data is None:
                continue
            reference = ref_data["ref"]
            for name in os.listdir(ref_dir):
                if name == "data.json":
                    continue
                rev_dir = os.path.join(ref_dir, name)
                rev_data = _read_json_with_retry(os.path.join(rev_dir, "data.json"))
                if rev_data is None:
                    continue
                if rev_data.get("path") == path:
                    ref = RecipeReference.loads(reference)
                    ref.revision = rev_data["revision"]
                    ref.timestamp = rev_data["timestamp"]
                    return ref
        return None
