import hashlib
import os
import shutil
import time
import uuid

from conan.cache.conan_reference import ConanReference
from conan.cache.conan_reference_layout import RecipeLayout, PackageLayout
# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.db.cache_database import CacheDatabase
from conans.errors import ConanException, ConanReferenceAlreadyExistsInDB, \
    ConanReferenceDoesNotExistInDB
from conans.model.info import PREV_UNKNOWN
from conans.util.files import rmdir


class DataCache:

    def __init__(self, base_folder, db_filename):
        self._base_folder = os.path.realpath(base_folder)
        self._db = CacheDatabase(filename=db_filename)

    def closedb(self):
        self._db.close()

    def _create_path(self, relative_path, remove_contents=True):
        path = self._full_path(relative_path)
        if os.path.exists(path) and remove_contents:
            self._remove_path(relative_path)
        os.makedirs(path, exist_ok=True)

    def _remove_path(self, relative_path):
        rmdir(self._full_path(relative_path))

    def _full_path(self, relative_path):
        path = os.path.realpath(os.path.join(self._base_folder, relative_path))
        return path

    @property
    def base_folder(self):
        return self._base_folder

    @staticmethod
    def _short_hash_path(h):
        """:param h: Unicode text to reduce"""
        h = h.encode("utf-8")
        md = hashlib.sha256()
        md.update(h)
        sha_bytes = md.hexdigest()
        # len based on: https://github.com/conan-io/conan/pull/9595#issuecomment-918976451
        return sha_bytes[0:16]

    @staticmethod
    def _get_tmp_path():
        h = DataCache._short_hash_path(str(uuid.uuid4()))
        return os.path.join("tmp", h)

    @staticmethod
    def _get_path(ref: ConanReference):
        value = ref.full_reference
        return DataCache._short_hash_path(value)

    def create_export_recipe_layout(self, ref: ConanReference):
        # This is a temporary layout, because the revision is not computed yet, until it is
        # The entry is not added to DB, just a temp folder is created
        assert not ref.rrev, "Recipe revision should be None"
        reference_path = self._get_tmp_path()
        self._create_path(reference_path)
        return RecipeLayout(ref, os.path.join(self.base_folder, reference_path))

    def create_tmp_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to get or create the package layout"
        assert pref.pkgid, "Package id must be known to get or create the package layout"
        assert not pref.prev, "Package revision should be unknown"
        temp_prev = f"{PREV_UNKNOWN}-{str(uuid.uuid4())}"
        pref = ConanReference(pref.name, pref.version, pref.user, pref.channel, pref.rrev,
                              pref.pkgid, temp_prev)
        package_path = self._get_tmp_path()
        self._db.create_tmp_package(package_path, pref)
        self._create_path(package_path)
        return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def create_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to create the package layout"
        assert pref.pkgid, "Package id must be known to create the package layout"
        assert pref.prev, "Package revision should be known to create the package layout"
        pref = ConanReference(pref.name, pref.version, pref.user, pref.channel, pref.rrev,
                              pref.pkgid, pref.prev)
        package_path = self._get_path(pref)
        self._db.create_package(package_path, pref)
        self._create_path(package_path, remove_contents=False)
        return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def get_reference_layout(self, ref: ConanReference):
        assert ref.rrev, "Recipe revision must be known to get the reference layout"
        ref_data = self._db.try_get_recipe(ref)
        ref_path = ref_data.get("path")
        return RecipeLayout(ref, os.path.join(self.base_folder, ref_path))

    def get_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to get the package layout"
        assert pref.pkgid, "Package id must be known to get the package layout"
        assert pref.prev, "Package revision must be known to get the package layout"
        pref_data = self._db.try_get_package(pref)
        pref_path = pref_data.get("path")
        return PackageLayout(pref, os.path.join(self.base_folder, pref_path))

    def get_or_create_reference_layout(self, ref: ConanReference):
        try:
            return self.get_reference_layout(ref)
        except ConanReferenceDoesNotExistInDB:
            assert ref.rrev, "Recipe revision must be known to create the package layout"
            reference_path = self._get_path(ref)
            self._db.create_recipe(reference_path, ref)
            self._create_path(reference_path, remove_contents=False)
            return RecipeLayout(ref, os.path.join(self.base_folder, reference_path))

    def get_or_create_package_layout(self, ref: ConanReference):
        try:
            return self.get_package_layout(ref)
        except ConanReferenceDoesNotExistInDB:
            return self.create_package_layout(ref)

    def _move_prev(self, old_pref: ConanReference, new_pref: ConanReference):
        ref_data = self._db.try_get_package(old_pref)
        old_path = ref_data.get("path")
        new_path = self._get_path(new_pref)
        if os.path.exists(self._full_path(new_path)):
            try:
                rmdir(self._full_path(new_path))
            except OSError as e:
                raise ConanException(f"{self._full_path(new_path)}\n\nFolder: {str(e)}\n"
                                     "Couldn't remove folder, might be busy or open\n"
                                     "Close any app using it, and retry")
        try:
            self._db.update_package(old_pref, new_pref, new_path=new_path, new_timestamp=time.time())
        except ConanReferenceAlreadyExistsInDB:
            # This happens when we create a recipe revision but we already had that one in the cache
            # we remove the new created one and update the date of the existing one
            # TODO: cache2.0 locks
            self._db.delete_package_by_path(old_path)
            self._db.update_package(new_pref, new_timestamp=time.time())

        shutil.move(self._full_path(old_path), self._full_path(new_path))

        return new_path

    def update_recipe_timestamp(self, ref: ConanReference,  new_timestamp=None):
        self._db.update_recipe_timestamp(ref, new_timestamp)

    def update_package(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_timestamp=None, new_build_id=None):
        self._db.update_package(old_ref, new_ref, new_path, new_timestamp, new_build_id)

    def list_references(self, only_latest_rrev=False):
        """ Returns an iterator to all the references inside cache. The argument 'only_latest_rrev'
            can be used to filter and return only the latest recipe revision for each reference.
        """
        for it in self._db.list_references(only_latest_rrev):
            yield it

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        for it in self._db.get_recipe_revisions(ref, only_latest_rrev):
            yield it

    def get_package_ids(self, ref: ConanReference):
        for it in self._db.get_package_ids(ref):
            yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        for it in self._db.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_build_id(self, ref):
        ref_data = self._db.try_get_package(ref)
        return ref_data.get("build_id")

    def get_recipe_timestamp(self, ref):
        # TODO: Remove this once the ref contains the timestamp
        ref_data = self._db.try_get_recipe(ref)
        return ref_data.get("timestamp")

    def get_package_timestamp(self, ref):
        ref_data = self._db.try_get_package(ref)
        return ref_data.get("timestamp")

    def remove_recipe(self, ref: ConanReference):
        self._db.remove_recipe(ref)

    def remove_package(self, ref: ConanReference):
        self._db.remove_package(ref)

    def assign_prev(self, layout: PackageLayout, ref: ConanReference):
        layout_conan_reference = ConanReference(layout.reference)
        assert ref.reference == layout_conan_reference.reference, "You cannot change the reference here"
        assert ref.prev, "It only makes sense to change if you are providing a package revision"
        assert ref.pkgid, "It only makes sense to change if you are providing a package id"
        new_path = self._move_prev(layout_conan_reference, ref)
        layout.reference = ref
        if new_path:
            layout._base_folder = os.path.join(self.base_folder, new_path)

    def assign_rrev(self, layout: RecipeLayout):
        # This is the entry point for a new exported recipe revision
        ref = ConanReference(layout.reference)
        assert ref.rrev, "It only makes sense to change if you are providing a revision"
        assert not ref.prev, "The reference for the recipe should not have package revision"
        assert not ref.pkgid, "The reference for the recipe should not have package id"

        # TODO: here maybe we should block the recipe and all the packages too
        new_path = self._get_path(ref)
        try:
            self._db.create_recipe(new_path, ref)
        except ConanReferenceAlreadyExistsInDB:
            # This was exported before, making it latest again, update timestamp
            self._db.update_recipe_timestamp(ref, time.time())

        # TODO: Here we are always overwriting the contents of the rrev folder where
        #  we are putting the exported files for the reference, but maybe we could
        #  just check the the files in the destination folder are the same so we don't
        #  have to do write operations (maybe other process is reading these files, this could
        #  also be managed by locks anyway)
        # TODO: cache2.0 probably we should not check this and move to other place or just
        #  avoid getting here if old and new paths are the same
        full_path = self._full_path(new_path)
        if os.path.exists(full_path):
            rmdir(self._full_path(new_path))
        shutil.move(self._full_path(layout.base_folder), full_path)

        layout.reference = ref
        layout._base_folder = os.path.join(self.base_folder, new_path)
