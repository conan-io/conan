import os
import shutil
import uuid
from io import StringIO
from typing import Optional, Union, Tuple, Iterator

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.cache_database import CacheDatabase
from conan.locks.locks_manager import LocksManager
from conans.model.ref import ConanFileReference, PackageReference
from conans.util import files
from .db.folders import ConanFolders


class DataCache:

    def __init__(self, base_folder: str, db_filename: str, locks_directory: str):
        self._base_folder = os.path.realpath(base_folder)
        self._locks_manager = LocksManager(locks_directory=locks_directory)
        self.db = CacheDatabase(filename=db_filename)
        self.db.initialize(if_not_exists=True)

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

    def list_references(self, only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references inside cache. The argument 'only_latest_rrev'
            can be used to filter and return only the latest recipe revision for each reference.
        """
        for it in self.db.list_references(only_latest_rrev):
            yield it

    def search_references(self, pattern: str,
                          only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references matching the pattern given. The pattern is
            checked against the references full name using SQL LIKE functionality. The argument
            'only_latest_rrev' can be used to filter and return only the latest recipe revision for
            the matching references.
        """
        for it in self.db.search_references(pattern, only_latest_rrev):
            yield it

    def list_reference_versions(self, ref: ConanFileReference,
                                only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references with the same 'ref.name' as the one provided.
            The argument 'only_latest_rrev' can be used to filter and return only the latest recipe
            revision for each of them.
        """
        for it in self.db.list_reference_versions(ref.name, only_latest_rrev):
            yield it

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        """ Returns the layout for a reference. The recipe revision is a requirement, only references
            with rrev are stored in the database. If it doesn't exists, it will raise
            References.DoesNotExist exception.
        """
        assert ref.revision, "Ask for a reference layout only if the rrev is known"
        return self._get_reference_layout(ref)

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

    def list_package_references(self, ref: ConanFileReference,
                                only_latest_prev: bool) -> Iterator[PackageReference]:
        """ Returns an iterator to the all the PackageReference for the given recipe reference. The
            argument 'only_latest_prev' can be used to filter and return only the latest package
            revision for each of them.
        """
        for it in self.db.list_package_references(ref, only_latest_prev):
            yield it

    def search_package_references(self, ref: ConanFileReference, package_id: str,
                                  only_latest_prev: bool) -> Iterator[PackageReference]:
        """ Returns an iterator to the all the PackageReference for the given recipe reference and
            package-id. The argument 'only_latest_prev' can be used to filter and return only the
            latest package revision for each of them.
        """
        for it in self.db.search_package_references(ref, package_id, only_latest_prev):
            yield it

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        """ Returns the layout for a package. The recipe revision and the package revision are a
            requirement, only packages with rrev and prev are stored in the database.
        """
        assert pref.ref.revision, "Ask for a package layout only if the rrev is known"
        assert pref.revision, "Ask for a package layout only if the prev is known"
        return self._get_package_layout(pref)

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
