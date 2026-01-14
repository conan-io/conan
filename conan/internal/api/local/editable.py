import copy
import fnmatch
import json
import os
from os.path import join, normpath

from conan.api.model import RecipeReference
from conan.internal.cache.concurrency_lock import ConcurrencyLock
from conan.internal.util.files import load, save


EDITABLE_PACKAGES_FILE = 'editable_packages.json'


class EditablePackages:
    """
    Manages the editable packages configuration file.

    This class handles adding, removing, and querying editable package references.
    All mutating operations (add, remove) are protected by inter-process locking
    to prevent race conditions when multiple Conan processes modify the file
    concurrently.
    """

    def __init__(self, cache_folder=None):
        self._cache_folder = cache_folder
        if cache_folder is None:
            self._edited_file = None
            self._lock = None
            self._edited_refs = {}
            return
        self._edited_file = normpath(join(cache_folder, EDITABLE_PACKAGES_FILE))
        self._lock = ConcurrencyLock(cache_folder)
        self._edited_refs = self._load_unlocked()

    def _load_unlocked(self):
        """
        Load editable packages from disk.

        This method should be called inside a lock context when used in
        mutating operations to ensure we have the latest state.

        Returns:
            dict: Mapping of RecipeReference to editable info
        """
        if self._edited_file and os.path.exists(self._edited_file):
            edited = load(self._edited_file)
            edited_js = json.loads(edited)
            return {RecipeReference.loads(r): d for r, d in edited_js.items()}
        return {}

    def _save_unlocked(self):
        """
        Save editable packages to disk atomically.

        Uses a temporary file and atomic rename to prevent corruption
        if the process is interrupted during the save.

        This method should be called inside a lock context.
        """
        d = {str(ref): info for ref, info in self._edited_refs.items()}
        tmp_file = self._edited_file + ".tmp"
        save(tmp_file, json.dumps(d))
        os.replace(tmp_file, self._edited_file)

    def update_copy(self, ws_editables):
        """
        Create a new instance with the union of the editable packages of self and other
        """
        if ws_editables is None:
            return self
        result = EditablePackages()
        result._edited_refs = self._edited_refs.copy()
        result._edited_refs.update(ws_editables)
        return result

    @property
    def edited_refs(self):
        return self._edited_refs

    def save(self):
        """
        Save editable packages to disk.

        Note: For internal use. Mutating operations (add, remove) handle their
        own saving with proper locking.
        """
        d = {str(ref): d for ref, d in self._edited_refs.items()}
        save(self._edited_file, json.dumps(d))

    def get(self, ref):
        _tmp = copy.copy(ref)
        _tmp.revision = None
        return self._edited_refs.get(_tmp)

    def get_path(self, ref):
        editable = self.get(ref)
        if editable is not None:
            return editable["path"]

    def add(self, ref, path, output_folder=None):
        """
        Add an editable package reference.

        This operation is protected by inter-process locking to prevent
        race conditions when multiple processes add editables concurrently.

        Args:
            ref: RecipeReference to add as editable
            path: Path to the editable package source
            output_folder: Optional output folder for the editable
        """
        assert isinstance(ref, RecipeReference)
        _tmp = copy.copy(ref)
        _tmp.revision = None

        if self._lock:
            with self._lock.config_lock(EDITABLE_PACKAGES_FILE):
                # Reload to get the latest state from disk
                self._edited_refs = self._load_unlocked()
                self._edited_refs[ref] = {"path": path, "output_folder": output_folder}
                self._save_unlocked()
        else:
            # In-memory only (no cache_folder)
            self._edited_refs[ref] = {"path": path, "output_folder": output_folder}

    def remove(self, path, requires):
        """
        Remove editable package references matching path or pattern.

        This operation is protected by inter-process locking to prevent
        race conditions when multiple processes remove editables concurrently.

        Args:
            path: Path to match for removal (exact match on editable path)
            requires: List of patterns to match against reference strings

        Returns:
            dict: The removed editable references and their info
        """
        if self._lock:
            with self._lock.config_lock(EDITABLE_PACKAGES_FILE):
                # Reload to get the latest state from disk
                self._edited_refs = self._load_unlocked()
                removed = self._remove_matching(path, requires)
                self._save_unlocked()
                return removed
        else:
            # In-memory only (no cache_folder)
            removed = self._remove_matching(path, requires)
            return removed

    def _remove_matching(self, path, requires):
        """
        Internal method to find and remove matching editables.

        Args:
            path: Path to match for removal
            requires: List of patterns to match

        Returns:
            dict: The removed editable references and their info
        """
        removed = {}
        kept = {}
        for ref, info in self._edited_refs.items():
            to_remove = False
            if path and info["path"] == path:
                to_remove = True
            else:
                for r in requires or []:
                    if fnmatch.fnmatch(str(ref), r):
                        to_remove = True
            if to_remove:
                removed[ref] = info
            else:
                kept[ref] = info
        self._edited_refs = kept
        return removed
