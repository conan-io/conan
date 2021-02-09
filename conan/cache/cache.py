import os

from cache.cache_database import CacheDatabase
from conan.cache.recipe_layout import RecipeLayout
from conans.model.ref import ConanFileReference, PackageReference
from conan.locks.locks_manager import LocksManager
from contextlib import contextmanager
from contextlib import contextmanager

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

    @property
    def base_folder(self) -> str:
        return self._base_folder

    def get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        reference_path = self._backend.get_directory(ref)
        base_reference_directory = os.path.join(self.base_folder, reference_path)
        return RecipeLayout(ref, base_reference_directory, cache=self, manager=self._locks_manager)

    @contextmanager
    def get_random_directory(self, remove=True):
        pass
