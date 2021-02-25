import os
import shutil
from io import StringIO
from typing import Optional

from conan.cache.exceptions import CacheDirectoryNotFound
from conan.cache.cache_database_directories import CacheDatabaseDirectories, \
    CacheDatabaseDirectoriesSqlite3Filesystem, \
    CacheDatabaseDirectoriesSqlite3Memory, ConanFolders
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference
from conans.util import files

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.


class Cache:
    def __init__(self, base_folder: str, backend: CacheDatabaseDirectories,
                 locks_manager: LocksManager):
        self._base_folder = base_folder
        self._locks_manager = locks_manager
        self._backend = backend

    @staticmethod
    def create(backend_id: str, base_folder: str, locks_manager: LocksManager, **backend_kwargs):
        if backend_id == 'sqlite3':
            backend = CacheDatabaseDirectoriesSqlite3Filesystem(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return Cache(base_folder, backend, locks_manager)
        elif backend_id == 'memory':
            backend = CacheDatabaseDirectoriesSqlite3Memory(**backend_kwargs)
            backend.create_table(if_not_exists=True)
            return Cache(base_folder, backend, locks_manager)
        else:
            raise NotImplementedError(f'Backend {backend_id} for cache is not implemented')

    def dump(self, output: StringIO):
        """ Maybe just for debugging purposes """
        self._backend.dump(output)

    @property
    def base_folder(self) -> str:
        return self._base_folder

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        from conan.cache.recipe_layout import RecipeLayout
        return RecipeLayout(ref, cache=self, manager=self._locks_manager)

    """
    def get_package_layout(self, pref: ConanFileReference) -> 'PackageLayout':
        from conan.cache.package_layout import PackageLayout
        return PackageLayout(pref, cache=self, manager=self._locks_manager)

    def remove_reference(self, ref: ConanFileReference):
        try:
            layout = self.get_reference_layout(ref)  # FIXME: Here we create the entry if it didn't exist
            with layout.lock(blocking=True):
                pass
        except CacheDirectoryNotFound:
            pass
    """

    def remove_package(self, pref: PackageReference):
        assert pref.ref.revision, 'It requires known recipe revision'
        assert pref.revision, 'It requires known package revision'
        pkg_layout = self.get_reference_layout(pref.ref).get_package_layout(pref)
        with pkg_layout.lock(blocking=True):
            # Remove contents and entries from database
            files.rmdir(str(pkg_layout.build()))
            files.rmdir(str(pkg_layout.package()))
            self._backend.remove_package_directory(pref, ConanFolders.PKG_BUILD)
            self._backend.remove_package_directory(pref, ConanFolders.PKG_PACKAGE)

    def _move_rrev(self, old_ref: ConanFileReference, new_ref: ConanFileReference,
                   move_reference_contents: bool = False) -> Optional[str]:
        # Once we know the revision for a given reference, we need to update information in the
        # backend and we might want to move folders.
        # TODO: Add a little bit of all-or-nothing aka rollback

        self._backend.update_rrev(old_ref, new_ref)

        if move_reference_contents:
            old_path = self._backend.try_get_reference_directory(new_ref)
            new_path = self._backend.get_default_reference_path(new_ref)
            self._backend.update_path(new_ref, new_path)
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
            return new_path
        return None

    def _move_prev(self, old_pref: PackageReference, new_pref: PackageReference,
                   folder: ConanFolders, move_package_contents: bool = False) -> Optional[str]:
        # TODO: Add a little bit of all-or-nothing aka rollback
        self._backend.update_prev(old_pref, new_pref)
        if move_package_contents:
            old_path = self._backend.try_get_package_directory(new_pref, folder)
            new_path = self._backend.get_default_package_path(new_pref, folder)
            self._backend.update_path(new_pref, new_path)
            if os.path.exists(old_path):
                shutil.move(old_path, new_path)
            return new_path
        return None
