import os
import shutil
import uuid
from io import StringIO
from typing import Tuple, Iterator

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.cache_database import CacheDatabase
from conan.cache.conan_reference import ConanReference
from conan.cache.db.references import ReferencesDbTable
from conans.model.ref import ConanFileReference, PackageReference
from conans.util import files
from conans.util.files import rmdir, md5


class DataCache:

    def __init__(self, base_folder: str, db_filename: str):
        self._base_folder = os.path.realpath(base_folder)
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
    def get_or_create_reference_path(item: ConanReference) -> str:
        """ Returns a folder for a Conan-Reference, it's deterministic if revision is known """
        if item.rrev:
            return md5(item.full_reference)
        else:
            return str(uuid.uuid4())

    @staticmethod
    def get_or_create_package_path(item: ConanReference) -> str:
        """ Returns a folder for a Conan-Reference, it's deterministic if revision is known """
        if item.prev:
            return md5(item.full_reference)
        else:
            return str(uuid.uuid4())

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        """ Returns the layout for a reference. The recipe revision is a requirement, only references
            with rrev are stored in the database. If it doesn't exists, it will raise
            References.DoesNotExist exception.
        """
        assert ref.revision, "Ask for a reference layout only if the rrev is known"
        from conan.cache.recipe_layout import RecipeLayout
        reference_path = self.db.try_get_reference_directory(ConanReference(ref))
        return RecipeLayout(ref, cache=self, base_folder=reference_path)

        # TODO: Should get_or_create_package_layout if not prev?

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        """ Returns the layout for a package. The recipe revision and the package revision are a
            requirement, only packages with rrev and prev are stored in the database.
        """
        assert pref.ref.revision, "Ask for a package layout only if the rrev is known"
        assert pref.revision, "Ask for a package layout only if the prev is known"
        package_path = self.db.try_get_reference_directory(ConanReference(pref))
        from conan.cache.package_layout import PackageLayout
        return PackageLayout(pref, cache=self, package_folder=package_path)

    def get_or_create_reference_layout(self, ref: ConanReference) -> Tuple['RecipeLayout', bool]:
        path = self.get_or_create_reference_path(ref)

        if not ref.rrev:
            ref = ConanReference(ref.name, ref.version, ref.user, ref.channel, path,
                                 ref.pkgid, ref.prev)

        reference_path, created = self.db.get_or_create_reference(path, ref)
        self._create_path(reference_path, remove_contents=created)

        from conan.cache.recipe_layout import RecipeLayout
        return RecipeLayout(ref, cache=self, base_folder=reference_path), created

    def get_or_create_package_layout(self, pref: ConanReference) -> Tuple['PackageLayout', bool]:
        package_path = self.get_or_create_package_path(pref)

        # Assign a random (uuid4) revision if not set
        # if the package revision is not calculated yet, assign the uuid of the path as prev
        if not pref.prev:
            pref = ConanReference(pref.name, pref.version, pref.user, pref.channel, package_path,
                                  pref.pkgid, pref.prev)

        package_path, created = self.db.get_or_create_reference(package_path, pref)
        self._create_path(package_path, remove_contents=created)

        from conan.cache.package_layout import PackageLayout
        return PackageLayout(pref, cache=self, package_folder=package_path), created

    def _move_rrev(self, old_ref: ConanReference, new_ref: ConanReference, remote=None) -> str:
        old_path = self.db.try_get_reference_directory(old_ref)
        new_path = self.get_or_create_reference_path(new_ref)
        try:
            self.db.update_reference(old_ref, new_ref, new_path=new_path, remote=remote)
        except ReferencesDbTable.AlreadyExist:
            self.db.delete_ref_by_path(old_path)
            # TODO: fix this, update timestamp
            self.db.update_reference(new_ref, new_ref)
        # TODO: Here we are always overwriting the contents of the rrev folder where
        #  we are putting the exported files for the reference, but maybe we could
        #  just check the the files in the destination folder are the same so we don't
        #  have to do write operations (maybe other process is reading these files, this could
        #  also be managed by locks anyway)
        # TODO: cache2.0 probably we should not check this and move to other place or just
        #  avoid getting here if old and new paths are the same
        if new_path != old_path:
            if os.path.exists(self._full_path(new_path)):
                rmdir(self._full_path(new_path))
            shutil.move(self._full_path(old_path), self._full_path(new_path))
        return new_path

    def _move_prev(self, old_pref: ConanReference, new_pref: ConanReference) -> str:
        old_path = self.db.try_get_reference_directory(old_pref)
        new_path = self.get_or_create_reference_path(new_pref)
        try:
            self.db.update_reference(old_pref, new_pref, new_path=new_path)
        except ReferencesDbTable.AlreadyExist:
            self.db.delete_ref_by_path(old_path)
            # TODO: fix this, update timestamp
            self.db.update_reference(new_pref, new_pref)

        if os.path.exists(self._full_path(new_path)):
            rmdir(self._full_path(new_path))
        shutil.move(self._full_path(old_path), self._full_path(new_path))

        return new_path

    def list_references(self, only_latest_rrev: bool = False) -> Iterator[ConanFileReference]:
        """ Returns an iterator to all the references inside cache. The argument 'only_latest_rrev'
            can be used to filter and return only the latest recipe revision for each reference.
        """
        for it in self.db.list_references(only_latest_rrev):
            yield it

    def get_recipe_revisions(self, ref, only_latest_rrev=False):
        for it in self.db.get_recipe_revisions(ref, only_latest_rrev):
            yield it

    def get_package_revisions(self, ref, only_latest_prev=False):
        for it in self.db.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_remote(self, ref):
        return self.db.get_remote(ref)
