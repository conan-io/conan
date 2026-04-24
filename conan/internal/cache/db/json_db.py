# Retry when reading data.json and parent dir exists (incomplete write by another process)
import hashlib
import json
import os
import time

from conan.errors import ConanException

_READ_JSON_MAX_RETRIES = 10
_READ_JSON_INITIAL_DELAY_S = 0.01
_READ_JSON_MAX_DELAY_S = 0.5


def ref_hash(ref_str: str) -> str:
    """Path-safe hash for reference (name/version@user/channel). Matches cache path style."""
    h = hashlib.sha256(ref_str.encode("utf-8")).hexdigest()
    return h[:13]


def read_json_with_retry(filepath: str) -> dict:
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


def write_json_atomic(filepath: str, data: dict) -> None:
    """Write JSON atomically via a .tmp file and replace."""
    tmp = filepath + ".tmp"
    msg = None
    for attempt in range(_READ_JSON_MAX_RETRIES):
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, filepath)
            return
        except OSError as e:
            time.sleep(min(
                _READ_JSON_INITIAL_DELAY_S * (2 ** attempt),
                _READ_JSON_MAX_DELAY_S
            ))
            msg = str(e)
    raise ConanException(f"Conan write error in RecipesDBJson: {msg}")
