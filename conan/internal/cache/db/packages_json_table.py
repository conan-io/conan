import os
import shutil
from typing import List, Optional

from conan.api.model import PkgReference, RecipeReference
from conan.internal.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB
from conan.internal.cache.db.recipes_json_table import _ref_hash, _read_json_with_retry, \
    _write_json_atomic


class PackagesJsonTable:
    """
    Lock-free, concurrent-safe packages table for shared folders (eventual consistency).
    Same public API as PackagesDBTable; packages are stored nested under their recipe revision:

        <db_folder>/<ref_hash>/<rrev_hash>/pkgs/<pkgid_hash>/data.json
        <db_folder>/<ref_hash>/<rrev_hash>/pkgs/<pkgid_hash>/<prev_hash>/data.json

    pkgid-level data.json : {"package_id": "..."}
    prev-level  data.json : {"revision": "...", "timestamp": ..., "path": "...", "build_id": "..."}
    """

    def __init__(self, db_folder: str):
        self._db_folder = os.path.abspath(db_folder)

    def create_table(self):
        """No-op for API compatibility."""

    # ------------------------------------------------------------------
    # Internal path helpers
    # ------------------------------------------------------------------

    def _pkgs_dir(self, ref: RecipeReference) -> str:
        ref_hash = _ref_hash(str(ref))
        rrev_hash = _ref_hash(ref.revision or "")
        return os.path.join(self._db_folder, ref_hash, rrev_hash, "pkgs")

    def _pkgid_dir(self, pref: PkgReference) -> str:
        return os.path.join(self._pkgs_dir(pref.ref), _ref_hash(pref.package_id or ""))

    def _prev_dir(self, pref: PkgReference) -> str:
        return os.path.join(self._pkgid_dir(pref), _ref_hash(pref.revision or ""))

    def _pkgid_data_path(self, pref: PkgReference) -> str:
        return os.path.join(self._pkgid_dir(pref), "data.json")

    def _prev_data_path(self, pref: PkgReference) -> str:
        return os.path.join(self._prev_dir(pref), "data.json")

    # ------------------------------------------------------------------
    # Internal scan helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_pkgid_entry(pkgid_dir: str) -> Optional[dict]:
        data_path = os.path.join(pkgid_dir, "data.json")
        if not os.path.isfile(data_path):
            return None
        return _read_json_with_retry(data_path)

    @staticmethod
    def _read_prev_entries(pkgid_dir: str) -> List[dict]:
        entries = []
        for name in os.listdir(pkgid_dir):
            if name == "data.json":
                continue
            prev_dir = os.path.join(pkgid_dir, name)
            if not os.path.isdir(prev_dir):
                continue
            prev_data = _read_json_with_retry(os.path.join(prev_dir, "data.json"))
            entries.append(prev_data)
        return entries

    @staticmethod
    def _make_result(ref: RecipeReference, pkgid_data: dict, prev_data: dict) -> dict:
        pref = PkgReference(ref, pkgid_data["package_id"],
                            prev_data["revision"], prev_data["timestamp"])
        return {
            "pref": pref,
            "build_id": prev_data.get("build_id"),
            "path": prev_data["path"],
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(self, path: str, pref: PkgReference, build_id):
        assert pref.revision
        assert pref.timestamp

        prev_dir = self._prev_dir(pref)
        if os.path.isdir(prev_dir):
            raise ConanReferenceAlreadyExistsInDB(f"Reference '{repr(pref)}' already exists")

        pkgid_dir = self._pkgid_dir(pref)
        if not os.path.isdir(pkgid_dir):
            os.makedirs(pkgid_dir, exist_ok=True)
            _write_json_atomic(self._pkgid_data_path(pref), {"package_id": pref.package_id})

        os.makedirs(prev_dir, exist_ok=True)
        _write_json_atomic(self._prev_data_path(pref), {
            "revision": pref.revision,
            "timestamp": pref.timestamp,
            "path": path,
            "build_id": build_id,
        })

    def get(self, pref: PkgReference) -> dict:
        if not os.path.isdir(self._prev_dir(pref)):
            raise ConanReferenceDoesNotExistInDB(f"No entry for package '{repr(pref)}'")

        pkgid_data = _read_json_with_retry(self._pkgid_data_path(pref))
        prev_data = _read_json_with_retry(self._prev_data_path(pref))
        return self._make_result(pref.ref, pkgid_data, prev_data)

    def update_timestamp(self, pref: PkgReference, path: str, build_id: str):
        assert pref.revision
        assert pref.timestamp

        if not os.path.isdir(self._prev_dir(pref)):
            return

        prev_data = _read_json_with_retry(self._prev_data_path(pref))
        prev_data["timestamp"] = pref.timestamp
        prev_data["path"] = path
        prev_data["build_id"] = build_id
        _write_json_atomic(self._prev_data_path(pref), prev_data)

    def remove_build_id(self, pref: PkgReference):
        if not os.path.isdir(self._prev_dir(pref)):
            return
        prev_data = _read_json_with_retry(self._prev_data_path(pref))
        prev_data["build_id"] = None
        _write_json_atomic(self._prev_data_path(pref), prev_data)

    def remove_recipe(self, ref: RecipeReference):
        """No-op: packages are nested under the recipe revision dir and removed with it."""

    def remove(self, pref: PkgReference):
        prev_dir = self._prev_dir(pref)
        if os.path.isdir(prev_dir):
            shutil.rmtree(prev_dir, ignore_errors=True)

        pkgid_dir = self._pkgid_dir(pref)
        if os.path.isdir(pkgid_dir):
            try:
                remaining = [n for n in os.listdir(pkgid_dir) if n != "data.json"]
                if not remaining:
                    shutil.rmtree(pkgid_dir, ignore_errors=True)
            except OSError:
                pass

    def get_package_revisions_references(self, pref: PkgReference,
                                         only_latest_prev=False) -> List[dict]:
        assert pref.ref.revision, "To search package revisions you must provide a recipe revision."
        assert pref.package_id, "To search package revisions you must provide a package id."

        pkgid_dir = self._pkgid_dir(pref)
        if not os.path.isdir(pkgid_dir):
            return []

        pkgid_data = self._read_pkgid_entry(pkgid_dir)
        if pkgid_data is None:
            return []

        entries = self._read_prev_entries(pkgid_dir)
        entries = [e for e in entries if e.get("revision") is not None]
        if pref.revision:
            entries = [e for e in entries if e["revision"] == pref.revision]

        entries.sort(key=lambda x: x["timestamp"], reverse=True)
        if only_latest_prev and entries:
            entries = [entries[0]]

        return [self._make_result(pref.ref, pkgid_data, e) for e in entries]

    def get_package_revisions_reference_exists(self, pref: PkgReference) -> bool:
        assert pref.ref.revision, "To check package revision existence you must provide a recipe revision."
        assert pref.package_id, "To check package revisions existence you must provide a package id."

        pkgid_dir = self._pkgid_dir(pref)
        if not os.path.isdir(pkgid_dir):
            return False

        if pref.revision:
            return os.path.isdir(self._prev_dir(pref))

        for name in os.listdir(pkgid_dir):
            if name != "data.json" and os.path.isdir(os.path.join(pkgid_dir, name)):
                return True
        return False

    def get_package_references(self, ref: RecipeReference, only_latest_prev=True) -> List[dict]:
        assert ref.revision, "To search for package id's you must provide a recipe revision."

        pkgs_dir = self._pkgs_dir(ref)
        if not os.path.isdir(pkgs_dir):
            return []

        result = []
        for pkgid_hash in os.listdir(pkgs_dir):
            pkgid_dir = os.path.join(pkgs_dir, pkgid_hash)
            if not os.path.isdir(pkgid_dir):
                continue

            pkgid_data = self._read_pkgid_entry(pkgid_dir)
            if pkgid_data is None:
                continue

            entries = self._read_prev_entries(pkgid_dir)
            entries = [e for e in entries if e.get("revision") is not None]
            if not entries:
                continue

            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            for e in ([entries[0]] if only_latest_prev else entries):
                result.append(self._make_result(ref, pkgid_data, e))

        result.sort(key=lambda x: x["pref"].timestamp)
        return result

    def get_package_references_with_build_id_match(self, ref: RecipeReference,
                                                   build_id) -> Optional[dict]:
        assert ref.revision, "To search for package id's by build_id you must provide a recipe revision."

        pkgs_dir = self._pkgs_dir(ref)
        if not os.path.isdir(pkgs_dir):
            return None

        for pkgid_hash in os.listdir(pkgs_dir):
            pkgid_dir = os.path.join(pkgs_dir, pkgid_hash)
            if not os.path.isdir(pkgid_dir):
                continue

            pkgid_data = self._read_pkgid_entry(pkgid_dir)
            if pkgid_data is None:
                continue

            entries = self._read_prev_entries(pkgid_dir)
            entries = [e for e in entries if e.get("revision") is not None
                       and e.get("build_id") == build_id]
            if not entries:
                continue

            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            return self._make_result(ref, pkgid_data, entries[0])

        return None

    def path_to_ref(self, path: str) -> Optional[PkgReference]:
        if not os.path.isdir(self._db_folder):
            return None

        for ref_hash_dir in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, ref_hash_dir)
            if not os.path.isdir(ref_dir):
                continue
            ref_data = _read_json_with_retry(os.path.join(ref_dir, "data.json"))

            for rrev_hash in os.listdir(ref_dir):
                if rrev_hash == "data.json":
                    continue
                rrev_dir = os.path.join(ref_dir, rrev_hash)
                if not os.path.isdir(rrev_dir):
                    continue
                pkgs_dir = os.path.join(rrev_dir, "pkgs")
                if not os.path.isdir(pkgs_dir):
                    continue
                rrev_data = _read_json_with_retry(os.path.join(rrev_dir, "data.json"))

                for pkgid_hash in os.listdir(pkgs_dir):
                    pkgid_dir = os.path.join(pkgs_dir, pkgid_hash)
                    if not os.path.isdir(pkgid_dir):
                        continue
                    pkgid_data = self._read_pkgid_entry(pkgid_dir)
                    if pkgid_data is None:
                        continue

                    for prev_hash in os.listdir(pkgid_dir):
                        if prev_hash == "data.json":
                            continue
                        prev_dir = os.path.join(pkgid_dir, prev_hash)
                        if not os.path.isdir(prev_dir):
                            continue
                        prev_data = _read_json_with_retry(os.path.join(prev_dir, "data.json"))
                        if prev_data and prev_data.get("path") == path:
                            ref = RecipeReference.loads(ref_data["ref"])
                            ref.revision = rrev_data["revision"]
                            ref.timestamp = rrev_data["timestamp"]
                            return PkgReference(ref, pkgid_data["package_id"],
                                                prev_data["revision"], prev_data["timestamp"])
        return None
