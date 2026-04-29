import os
import shutil
from typing import List, Optional

from conan.api.model import PkgReference, RecipeReference
from conan.internal.cache.db.json_db import read_json_with_retry, write_json_atomic, ref_hash
from conan.internal.errors import ConanReferenceDoesNotExistInDB, ConanReferenceAlreadyExistsInDB


class PackagesJsonTable:
    """
    Lock-free, concurrent-safe packages table for shared folders (eventual consistency).
    Same public API as PackagesDBTable; packages are stored nested under their recipe revision:

        <db_folder>/<ref_hash>/<rrev>/<pkgid>/<prev>/data.json

    The rrev, pkgid, and prev are used directly as folder names (all are safe hex strings).
    prev-level data.json : {"timestamp": ..., "path": "...", "build_id": "..."}
    """

    def __init__(self, db_folder: str):
        self._db_folder = os.path.abspath(db_folder)

    def create_table(self):
        """No-op for API compatibility."""

    # ------------------------------------------------------------------
    # Internal path helpers
    # ------------------------------------------------------------------

    def _rrev_dir(self, ref: RecipeReference) -> str:
        assert ref.revision
        # ref is hashed (contains special chars); revision is a safe hex string used directly.
        return os.path.join(self._db_folder, ref_hash(str(ref)), ref.revision)

    def _pkgid_dir(self, pref: PkgReference) -> str:
        # package_id is a safe hex string — use it directly as the folder name.
        assert pref.package_id
        return os.path.join(self._rrev_dir(pref.ref), pref.package_id)

    def _prev_dir(self, pref: PkgReference) -> str:
        # package revision is a safe hex string — use it directly as the folder name.
        assert pref.revision
        return os.path.join(self._pkgid_dir(pref), pref.revision)

    # ------------------------------------------------------------------
    # Internal scan helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_prev_entries(pkgid_dir: str) -> List[tuple]:
        """Return [(prev_folder_name, data_dict), ...] for every revision under a pkgid dir."""
        entries = []
        for name in os.listdir(pkgid_dir):
            prev_dir = os.path.join(pkgid_dir, name)
            if not os.path.isdir(prev_dir):
                continue
            prev_data = read_json_with_retry(os.path.join(prev_dir, "data.json"))
            entries.append((name, prev_data))  # name IS the package revision string
        return entries

    @staticmethod
    def _make_result(ref: RecipeReference, package_id: str, prev_name: str,
                     prev_data: dict) -> dict:
        pref = PkgReference(ref, package_id, prev_name, prev_data["timestamp"])
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

        os.makedirs(prev_dir, exist_ok=True)
        # revision and package_id are the folder names — no need to store them in the file.
        write_json_atomic(os.path.join(prev_dir, "data.json"), {
            "timestamp": pref.timestamp,
            "path": path,
            "build_id": build_id,
        })

    def get(self, pref: PkgReference) -> dict:
        prev_dir = self._prev_dir(pref)
        if not os.path.isdir(prev_dir):
            raise ConanReferenceDoesNotExistInDB(f"No entry for package '{repr(pref)}'")

        prev_data = read_json_with_retry(os.path.join(prev_dir, "data.json"))
        return self._make_result(pref.ref, pref.package_id, pref.revision, prev_data)

    def update_timestamp(self, pref: PkgReference, path: str, build_id: str):
        assert pref.revision
        assert pref.timestamp

        prev_dir = self._prev_dir(pref)
        if not os.path.isdir(prev_dir):
            return

        prev_data = read_json_with_retry(os.path.join(prev_dir, "data.json"))
        prev_data["timestamp"] = pref.timestamp
        prev_data["path"] = path
        prev_data["build_id"] = build_id
        write_json_atomic(os.path.join(prev_dir, "data.json"), prev_data)

    def remove_build_id(self, pref: PkgReference):
        prev_dir = self._prev_dir(pref)
        if not os.path.isdir(prev_dir):
            return
        prev_data = read_json_with_retry(os.path.join(prev_dir, "data.json"))
        prev_data["build_id"] = None
        write_json_atomic(os.path.join(prev_dir, "data.json"), prev_data)

    def remove_recipe(self, ref: RecipeReference):
        """No-op: packages are nested under the recipe revision dir and removed with it."""

    def remove(self, pref: PkgReference):
        prev_dir = self._prev_dir(pref)
        if os.path.isdir(prev_dir):
            shutil.rmtree(prev_dir, ignore_errors=True)

        # Remove the pkgid dir if no revision subdirs remain.
        pkgid_dir = self._pkgid_dir(pref)
        try:
            if not os.listdir(pkgid_dir):
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

        entries = self._read_prev_entries(pkgid_dir)
        if pref.revision:
            entries = [(name, d) for name, d in entries if name == pref.revision]

        entries.sort(key=lambda x: x[1]["timestamp"], reverse=True)
        if only_latest_prev and entries:
            entries = [entries[0]]

        return [self._make_result(pref.ref, pref.package_id, name, d) for name, d in entries]

    def get_package_revisions_reference_exists(self, pref: PkgReference) -> bool:
        assert pref.ref.revision, "To check package revision existence you must provide a recipe revision."
        assert pref.package_id, "To check package revisions existence you must provide a package id."

        pkgid_dir = self._pkgid_dir(pref)
        if not os.path.isdir(pkgid_dir):
            return False

        if pref.revision:
            return os.path.isdir(self._prev_dir(pref))

        return any(os.path.isdir(os.path.join(pkgid_dir, name))
                   for name in os.listdir(pkgid_dir))

    def get_package_references(self, ref: RecipeReference, only_latest_prev=True) -> List[dict]:
        assert ref.revision, "To search for package id's you must provide a recipe revision."

        rrev_dir = self._rrev_dir(ref)
        if not os.path.isdir(rrev_dir):
            return []

        result = []
        for pkgid in os.listdir(rrev_dir):
            pkgid_dir = os.path.join(rrev_dir, pkgid)
            if not os.path.isdir(pkgid_dir):
                continue

            entries = self._read_prev_entries(pkgid_dir)
            if not entries:
                continue

            entries.sort(key=lambda x: x[1]["timestamp"], reverse=True)
            for name, d in ([entries[0]] if only_latest_prev else entries):
                result.append(self._make_result(ref, pkgid, name, d))

        result.sort(key=lambda x: x["pref"].timestamp)
        return result

    def get_package_references_with_build_id_match(self, ref: RecipeReference,
                                                   build_id) -> Optional[dict]:
        assert ref.revision, "To search for package id's by build_id you must provide a recipe revision."

        rrev_dir = self._rrev_dir(ref)
        if not os.path.isdir(rrev_dir):
            return None

        for pkgid in os.listdir(rrev_dir):
            pkgid_dir = os.path.join(rrev_dir, pkgid)
            if not os.path.isdir(pkgid_dir):
                continue

            entries = [(name, d) for name, d in self._read_prev_entries(pkgid_dir)
                       if d.get("build_id") == build_id]
            if not entries:
                continue

            entries.sort(key=lambda x: x[1]["timestamp"], reverse=True)
            name, d = entries[0]
            return self._make_result(ref, pkgid, name, d)

        return None

    def path_to_ref(self, path: str) -> Optional[PkgReference]:
        if not os.path.isdir(self._db_folder):
            return None

        for ref_h in os.listdir(self._db_folder):
            ref_dir = os.path.join(self._db_folder, ref_h)
            if not os.path.isdir(ref_dir):
                continue
            ref_data = read_json_with_retry(os.path.join(ref_dir, "data.json"))

            for rrev in os.listdir(ref_dir):
                rrev_dir = os.path.join(ref_dir, rrev)
                if not os.path.isdir(rrev_dir):
                    continue
                rrev_data = read_json_with_retry(os.path.join(rrev_dir, "data.json"))

                for pkgid in os.listdir(rrev_dir):
                    pkgid_dir = os.path.join(rrev_dir, pkgid)
                    if not os.path.isdir(pkgid_dir):
                        continue

                    for prev in os.listdir(pkgid_dir):
                        prev_dir = os.path.join(pkgid_dir, prev)
                        if not os.path.isdir(prev_dir):
                            continue
                        prev_data = read_json_with_retry(os.path.join(prev_dir, "data.json"))
                        if prev_data and prev_data.get("path") == path:
                            ref = RecipeReference.loads(ref_data["ref"])
                            ref.revision = rrev
                            ref.timestamp = rrev_data["timestamp"]
                            return PkgReference(ref, pkgid, prev, prev_data["timestamp"])

        return None
