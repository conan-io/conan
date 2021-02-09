import os
import shutil
from typing import Optional

from cache.cache_database import CacheDatabase
from conan.cache.recipe_layout import RecipeLayout
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference


class Cache:
    def __init__(self, base_folder: str, backend: CacheDatabase, locks_manager: LocksManager):
        self._base_folder = base_folder
        self._locks_manager = locks_manager
        self._backend = backend

    @staticmethod
    def create(backend_id: str, base_folder: str, locks_manager: LocksManager, **backend_kwargs):
        if backend_id == 'sqlite3':
            backend = CacheDatabase(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return Cache(base_folder, backend, locks_manager)
        elif backend_id == 'memory':
            backend = CacheDatabase(':memory:')
            backend.create_table(if_not_exists=True)
            return Cache(base_folder, backend, locks_manager)
        else:
            raise NotImplementedError(f'Backend {backend_id} for cache is not implemented')

    def dump(self):
        """ Maybe just for debugging purposes """
        self._backend.dump()

    @property
    def base_folder(self) -> str:
        return self._base_folder

    def get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        return RecipeLayout(ref, cache=self, manager=self._locks_manager)

    def _move_rrev(self, old_ref: ConanFileReference, new_ref: ConanFileReference,
                   move_reference_contents: bool = False) -> Optional[str]:
        # Once we know the revision for a given reference, we need to update information in the
        # backend and we might want to move folders.
        # TODO: Add a little bit of all-or-nothing aka rollback

        self._backend.update_rrev(old_ref, new_ref)

        if move_reference_contents:
            old_path, created = self._backend.get_or_create_directory(new_ref)
            assert not created, "Old reference was an existing one"
            new_path = new_ref.full_str().replace('@', '/').replace('#', '/')  # TODO: TBD
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
            self._backend.update_path(new_ref, new_path)
            return new_path
        else:
            return None

    def _move_prev(self, old_pref: PackageReference, new_pref: PackageReference,
                   move_package_contents: bool = False) -> Optional[str]:
        self._backend.update_prev(old_pref, new_pref)
        if move_package_contents:
            old_path, created = self._backend.get_or_create_directory(new_pref.ref, new_pref)
            assert not created, "It should exist"
            new_path = new_pref.full_str().replace('@', '/').replace('#', '/').replace(':', '/')
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
            self._backend.update_path(new_pref.ref, new_path, new_pref)
            return new_path
        else:
            return None
