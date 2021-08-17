import os
import shutil
import time
import uuid
from io import StringIO

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.db.cache_database import CacheDatabase
from conan.cache.conan_reference import ConanReference
from conan.cache.conan_reference_layout import RecipeLayout, PackageLayout
from conans.errors import ConanException, ConanReferenceAlreadyExistInDB, ConanReferenceDoesNotExistInDB
from conans.model.info import RREV_UNKNOWN, PREV_UNKNOWN
from conans.util.files import md5, rmdir


class DataCache:

    def __init__(self, base_folder, db_filename):
        self._base_folder = os.path.realpath(base_folder)
        self._db = CacheDatabase(filename=db_filename)

    def closedb(self):
        self._db.close()

    def dump(self, output: StringIO):
        """ Maybe just for debugging purposes """
        output.write("*" * 40)
        output.write(f"\nBase folder: {self._base_folder}\n\n")
        self._db.dump(output)

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
    def _get_tmp_path():
        return os.path.join("tmp", str(uuid.uuid4()))

    @staticmethod
    def _get_path(ref: ConanReference):
        return md5(ref.full_reference)

    def create_tmp_reference_layout(self, ref: ConanReference):
        assert not ref.rrev, "Recipe revision should be unknown"
        # even if they are temporal, we have to assign unique revisions to temporal references
        # until we know the calculated revision so that we don't store multiple references
        # with same rrev or prev
        temp_rrev = f"{RREV_UNKNOWN}-{str(uuid.uuid4())}"
        ref = ConanReference(ref.name, ref.version, ref.user, ref.channel, temp_rrev,
                             ref.pkgid, ref.prev)
        reference_path = self._get_tmp_path()
        self._db.create_tmp_reference(reference_path, ref)
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
        self._db.create_tmp_reference(package_path, pref)
        self._create_path(package_path)
        return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def create_reference_layout(self, ref: ConanReference):
        assert ref.rrev, "Recipe revision must be known to create the package layout"
        ref = ConanReference(ref.name, ref.version, ref.user, ref.channel, ref.rrev,
                             ref.pkgid, ref.prev)
        reference_path = self._get_path(ref)
        self._db.create_reference(reference_path, ref)
        self._create_path(reference_path, remove_contents=False)
        return RecipeLayout(ref, os.path.join(self.base_folder, reference_path))

    def create_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to create the package layout"
        assert pref.pkgid, "Package id must be known to create the package layout"
        assert pref.prev, "Package revision should be known to create the package layout"
        pref = ConanReference(pref.name, pref.version, pref.user, pref.channel, pref.rrev,
                              pref.pkgid, pref.prev)
        package_path = self._get_path(pref)
        self._db.create_reference(package_path, pref)
        self._create_path(package_path, remove_contents=False)
        return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def get_reference_layout(self, ref: ConanReference):
        assert ref.rrev, "Recipe revision must be known to get the reference layout"
        ref_data = self._db.try_get_reference(ref)
        ref_path = ref_data.get("path")
        return RecipeLayout(ref, os.path.join(self.base_folder, ref_path))

    def get_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to get the package layout"
        assert pref.pkgid, "Package id must be known to get the package layout"
        assert pref.prev, "Package revision must be known to get the package layout"
        pref_data = self._db.try_get_reference(pref)
        pref_path = pref_data.get("path")
        return PackageLayout(pref, os.path.join(self.base_folder, pref_path))

    def get_or_create_reference_layout(self, ref: ConanReference):
        try:
            return self.get_reference_layout(ref)
        except ConanReferenceDoesNotExistInDB:
            return self.create_reference_layout(ref)

    def get_or_create_package_layout(self, ref: ConanReference):
        try:
            return self.get_package_layout(ref)
        except ConanReferenceDoesNotExistInDB:
            return self.create_package_layout(ref)

    def _move_rrev(self, old_ref: ConanReference, new_ref: ConanReference):
        ref_data = self._db.try_get_reference(old_ref)
        old_path = ref_data.get("path")
        new_path = self._get_path(new_ref)

        try:
            self._db.update_reference(old_ref, new_ref, new_path=new_path, new_timestamp=time.time())
        except ConanReferenceAlreadyExistInDB:
            # This happens when we create a recipe revision but we already had that one in the cache
            # we remove the new created one and update the date of the existing one
            self._db.delete_ref_by_path(old_path)
            self._db.update_reference(new_ref, new_timestamp=time.time())

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

    def _move_prev(self, old_pref: ConanReference, new_pref: ConanReference):
        ref_data = self._db.try_get_reference(old_pref)
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
            self._db.update_reference(old_pref, new_pref, new_path=new_path, new_timestamp=time.time())
        except ConanReferenceAlreadyExistInDB:
            # This happens when we create a recipe revision but we already had that one in the cache
            # we remove the new created one and update the date of the existing one
            # TODO: cache2.0 locks
            self._db.delete_ref_by_path(old_path)
            self._db.update_reference(new_pref, new_timestamp=time.time())

        shutil.move(self._full_path(old_path), self._full_path(new_path))

        return new_path

    def update_reference(self, old_ref: ConanReference, new_ref: ConanReference = None,
                         new_path=None, new_remote=None, new_timestamp=None, new_build_id=None):
        self._db.update_reference(old_ref, new_ref, new_path, new_remote, new_timestamp, new_build_id)

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
        ref_data = self._db.try_get_reference(ref)
        return ref_data.get("build_id")

    def get_remote(self, ref: ConanReference):
        ref_data = self._db.try_get_reference(ref)
        return ref_data.get("remote")

    def get_timestamp(self, ref):
        ref_data = self._db.try_get_reference(ref)
        return ref_data.get("timestamp")

    def set_remote(self, ref: ConanReference, new_remote):
        self._db.set_remote(ref, new_remote)

    def remove(self, ref: ConanReference):
        self._db.remove(ref)

    def assign_prev(self, layout: PackageLayout, ref: ConanReference):
        layout_conan_reference = ConanReference(layout.reference)
        assert ref.reference == layout_conan_reference.reference, "You cannot change the reference here"
        assert ref.prev, "It only makes sense to change if you are providing a package revision"
        assert ref.pkgid, "It only makes sense to change if you are providing a package id"
        new_path = self._move_prev(layout_conan_reference, ref)
        layout.reference = ref
        if new_path:
            layout._base_folder = os.path.join(self.base_folder, new_path)

    def assign_rrev(self, layout: RecipeLayout, ref: ConanReference):
        layout_conan_reference = ConanReference(layout.reference)
        assert ref.reference == layout_conan_reference.reference, "You cannot change reference name here"
        assert ref.rrev, "It only makes sense to change if you are providing a revision"
        assert not ref.prev, "The reference for the recipe should not have package revision"
        assert not ref.pkgid, "The reference for the recipe should not have package id"
        # TODO: here maybe we should block the recipe and all the packages too
        new_path = self._move_rrev(layout_conan_reference, ref)
        layout.reference = ref
        if new_path:
            layout._base_folder = os.path.join(self.base_folder, new_path)
