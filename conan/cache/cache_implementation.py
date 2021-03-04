import os
import shutil
import uuid
from io import StringIO
from typing import Optional, Union, Tuple

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.cache import Cache
from conan.cache.cache_database import CacheDatabase, CacheDatabaseSqlite3Filesystem, \
    CacheDatabaseSqlite3Memory
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference
from conans.util import files
from ._tables.folders import ConanFolders


class CacheImplementation(Cache):

    def __init__(self, base_folder: str, db: CacheDatabase,
                 locks_manager: LocksManager):
        self._base_folder = os.path.realpath(base_folder)
        self._locks_manager = locks_manager
        self.db = db

    @classmethod
    def create(cls, backend_id: str, base_folder: str, locks_manager: LocksManager, **backend):
        if backend_id == 'sqlite3':
            backend = CacheDatabaseSqlite3Filesystem(**backend)
            backend.initialize(if_not_exists=True)
            return cls(base_folder, backend, locks_manager)
        elif backend_id == 'memory':
            backend = CacheDatabaseSqlite3Memory(**backend)
            backend.initialize(if_not_exists=True)
            return cls(base_folder, backend, locks_manager)
        else:
            raise NotImplementedError(f'Backend {backend_id} for cache is not implemented')

    def dump(self, output: StringIO):
        """ Maybe just for debugging purposes """
        output.write("*" * 40)
        output.write(f"\nBase folder: {self._base_folder}\n\n")
        self.db.dump(output)

    def _create_path(self, relative_path: str, remove_contents=True):
        path = self._full_path(relative_path)
        if os.path.exists(path) and remove_contents:
            self._remove_path(relative_path)
        os.makedirs(path, exist_ok=True)

    def _remove_path(self, relative_path: str):
        files.rmdir(self._full_path(relative_path))

    def _full_path(self, relative_path: str) -> str:
        path = os.path.realpath(os.path.join(self._base_folder, relative_path))
        assert path.startswith(self._base_folder), f"Path '{relative_path}' isn't contained inside" \
                                                   f" the cache '{self._base_folder}'"
        return path

    @property
    def base_folder(self) -> str:
        return self._base_folder

    @staticmethod
    def get_default_path(item: Union[ConanFileReference, PackageReference]) -> str:
        """ Returns a folder for a Conan-Reference, it's deterministic if revision is known """
        if item.revision:
            return item.full_str().replace('@', '/').replace('#', '/').replace(':', '/')  # TODO: TBD
        else:
            return str(uuid.uuid4())

    def _get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        from conan.cache.recipe_layout import RecipeLayout
        reference_path = self.db.try_get_reference_directory(ref)
        return RecipeLayout(ref, cache=self, manager=self._locks_manager, base_folder=reference_path,
                            locked=True)

    def get_or_create_reference_layout(self, ref: ConanFileReference) -> Tuple['RecipeLayout', bool]:
        path = self.get_default_path(ref)

        # Assign a random (uuid4) revision if not set
        locked = bool(ref.revision)
        if not ref.revision:
            ref = ref.copy_with_rev(str(uuid.uuid4()))

        reference_path, created = self.db.get_or_create_reference(ref, path=path)
        self._create_path(reference_path, remove_contents=created)

        from conan.cache.recipe_layout import RecipeLayout
        return RecipeLayout(ref, cache=self, manager=self._locks_manager,
                            base_folder=reference_path,
                            locked=locked), created

    def _get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        package_path = self.db.try_get_package_reference_directory(pref,
                                                                   folder=ConanFolders.PKG_PACKAGE)
        from conan.cache.package_layout import PackageLayout
        return PackageLayout(pref, cache=self, manager=self._locks_manager,
                             package_folder=package_path, locked=True)

    def get_or_create_package_layout(self, pref: PackageReference) -> Tuple['PackageLayout', bool]:
        package_path = self.get_default_path(pref)

        # Assign a random (uuid4) revision if not set
        locked = bool(pref.revision)
        if not pref.revision:
            pref = pref.copy_with_revs(pref.ref.revision, str(uuid.uuid4()))

        package_path, created = self.db.get_or_create_package(pref, path=package_path,
                                                              folder=ConanFolders.PKG_PACKAGE)
        self._create_path(package_path, remove_contents=created)

        from conan.cache.package_layout import PackageLayout
        return PackageLayout(pref, cache=self, manager=self._locks_manager,
                             package_folder=package_path, locked=locked), created

    def _move_rrev(self, old_ref: ConanFileReference, new_ref: ConanFileReference,
                   move_reference_contents: bool = False) -> Optional[str]:
        # Once we know the revision for a given reference, we need to update information in the
        # backend and we might want to move folders.
        # TODO: Add a little bit of all-or-nothing aka rollback

        self.db.update_reference(old_ref, new_ref)
        if move_reference_contents:
            old_path = self.db.try_get_reference_directory(new_ref)
            new_path = self.get_default_path(new_ref)
            shutil.move(self._full_path(old_path), self._full_path(new_path))
            self.db.update_reference_directory(new_ref, new_path)
            return new_path
        return None

    def _move_prev(self, old_pref: PackageReference, new_pref: PackageReference,
                   move_package_contents: bool = False) -> Optional[str]:
        # TODO: Add a little bit of all-or-nothing aka rollback

        self.db.update_package_reference(old_pref, new_pref)
        if move_package_contents:
            old_path = self.db.try_get_package_reference_directory(new_pref,
                                                                   ConanFolders.PKG_PACKAGE)
            new_path = self.get_default_path(new_pref)
            shutil.move(self._full_path(old_path), self._full_path(new_path))
            self.db.update_package_reference_directory(new_pref, new_path, ConanFolders.PKG_PACKAGE)
            return new_path
        return None
