from conan.cache.recipe_layout import RecipeLayout
from conans.model.ref import ConanFileReference, PackageReference
from conan.locks.locks_manager import LocksManager
from contextlib import contextmanager
from contextlib import contextmanager

from conan.cache.recipe_layout import RecipeLayout
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


class Cache:
    def __init__(self, base_folder: str, locks_manager: LocksManager):
        self._base_folder = base_folder
        self._locks_manager = locks_manager

    def unique_id(self, ref: ConanFileReference, pref: PackageReference = None) -> str:
        # Retrieve the unique-id for the given arguments. It can be the rowid from the cache database
        # or anything else deterministic
        # FIXME: Probably this doesn't belong to this class
        return ref.full_str()

    def get_base_path(self, unique_id: str) -> str:
        pass

    def get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        # TODO: Lot of things to implement
        reference_id = self.unique_id(ref=ref)
        return RecipeLayout(ref, resource=reference_id, manager=self._locks_manager)

    @contextmanager
    def get_random_directory(self, remove=True):
        pass
