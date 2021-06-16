import os
import shutil
import uuid
from io import StringIO

# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.cache.cache_database import CacheDatabase
from conan.cache.conan_reference import ConanReference
from conan.cache.conan_reference_layout import ReferenceLayout
from conan.cache.db.references import ReferencesDbTable
from conans.util import files
from conans.util.files import rmdir, md5


class DataCache:

    def __init__(self, base_folder, db_filename):
        self._base_folder = os.path.realpath(base_folder)
        self.db = CacheDatabase(filename=db_filename)
        self.db.initialize(if_not_exists=True)

    def dump(self, output: StringIO):
        """ Maybe just for debugging purposes """
        output.write("*" * 40)
        output.write(f"\nBase folder: {self._base_folder}\n\n")
        self.db.dump(output)

    def _create_path(self, relative_path, remove_contents=True):
        path = self._full_path(relative_path)
        if os.path.exists(path) and remove_contents:
            self._remove_path(relative_path)
        os.makedirs(path, exist_ok=True)

    def _remove_path(self, relative_path):
        files.rmdir(self._full_path(relative_path))

    def _full_path(self, relative_path):
        path = os.path.realpath(os.path.join(self._base_folder, relative_path))
        return path

    @property
    def base_folder(self):
        return self._base_folder

    @staticmethod
    def get_or_create_reference_path(ref: ConanReference):
        """ Returns a folder for a Conan-Reference, it's deterministic if revision is known """
        if ref.rrev:
            return md5(ref.full_reference)
        else:
            return str(uuid.uuid4())

    @staticmethod
    def get_or_create_package_path(ref: ConanReference):
        """ Returns a folder for a Conan-Reference, it's deterministic if revision is known """
        if ref.prev:
            return md5(ref.full_reference)
        else:
            return str(uuid.uuid4())

    def get_or_create_reference_layout(self, ref: ConanReference):
        path = self.get_or_create_reference_path(ref)

        if not ref.rrev:
            ref = ConanReference(ref.name, ref.version, ref.user, ref.channel, path,
                                 ref.pkgid, ref.prev)

        reference_path, created = self.db.get_or_create_reference(path, ref)
        self._create_path(reference_path, remove_contents=created)

        return ReferenceLayout(ref, os.path.join(self.base_folder, reference_path))

    def get_or_create_package_layout(self, pref: ConanReference):
        package_path = self.get_or_create_package_path(pref)

        # Assign a random (uuid4) revision if not set
        # if the package revision is not calculated yet, assign the uuid of the path as prev
        # TODO: cache2.0: fix this in the future
        rrev = pref.rrev or package_path
        prev = pref.prev or package_path
        if not pref.prev:
            pref = ConanReference(pref.name, pref.version, pref.user, pref.channel, rrev,
                                  pref.pkgid, prev)

        package_path, created = self.db.get_or_create_reference(package_path, pref)
        self._create_path(package_path, remove_contents=created)

        return ReferenceLayout(pref, os.path.join(self.base_folder, package_path))

    def get_reference_layout(self, ref: ConanReference):
        assert ref.rrev, "Recipe revision must be known to get the reference layout"
        path = self.get_or_create_reference_path(ref)
        return ReferenceLayout(ref, os.path.join(self.base_folder, path))

    def get_package_layout(self, pref: ConanReference):
        assert pref.rrev, "Recipe revision must be known to get the reference layout"
        assert pref.prev, "Package revision must be known to get the reference layout"
        assert pref.pkgid, "Package id must be known to get the reference layout"
        package_path = self.get_or_create_package_path(pref)
        return ReferenceLayout(pref, os.path.join(self.base_folder, package_path))

    def _move_rrev(self, old_ref: ConanReference, new_ref: ConanReference):
        old_path = self.db.try_get_reference_directory(old_ref)
        new_path = self.get_or_create_reference_path(new_ref)

        try:
            self.db.update_reference(old_ref, new_ref, new_path=new_path)
        except ReferencesDbTable.AlreadyExist:
            # This happens when we create a recipe revision but we already had that one in the cache
            # we remove the new created one and update the date of the existing one
            self.db.delete_ref_by_path(old_path)
            # TODO: cache2.0 should we update the timestamp here?
            self.db.update_reference(new_ref)

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
        old_path = self.db.try_get_reference_directory(old_pref)
        new_path = self.get_or_create_reference_path(new_pref)
        try:
            self.db.update_reference(old_pref, new_pref, new_path=new_path)
        except ReferencesDbTable.AlreadyExist:
            # This happens when we create a recipe revision but we already had that one in the cache
            # we remove the new created one and update the date of the existing one
            self.db.delete_ref_by_path(old_path)
            self.db.update_reference(new_pref)

        if os.path.exists(self._full_path(new_path)):
            rmdir(self._full_path(new_path))
        shutil.move(self._full_path(old_path), self._full_path(new_path))

        return new_path

    def list_references(self, only_latest_rrev=False):
        """ Returns an iterator to all the references inside cache. The argument 'only_latest_rrev'
            can be used to filter and return only the latest recipe revision for each reference.
        """
        for it in self.db.list_references(only_latest_rrev):
            yield it

    def get_recipe_revisions(self, ref: ConanReference, only_latest_rrev=False):
        for it in self.db.get_recipe_revisions(ref, only_latest_rrev):
            yield it

    def get_package_ids(self, ref: ConanReference, only_latest_prev=False):
        for it in self.db.get_package_ids(ref, only_latest_prev):
            yield it

    def get_package_revisions(self, ref: ConanReference, only_latest_prev=False):
        for it in self.db.get_package_revisions(ref, only_latest_prev):
            yield it

    def get_remote(self, ref: ConanReference):
        return self.db.get_remote(ref)

    def get_timestamp(self, ref):
        return self.db.get_timestamp(ref)

    def set_remote(self, ref: ConanReference, new_remote):
        self.db.set_remote(ref, new_remote)

    def remove(self, ref: ConanReference):
        self.db.remove(ref)

    def assign_prev(self, layout: ReferenceLayout, ref: ConanReference):
        assert ref.reference == layout._ref.reference, "You cannot change the reference here"
        assert ref.prev, "It only makes sense to change if you are providing a package revision"
        assert ref.pkgid, "It only makes sense to change if you are providing a package id"
        new_path = self._move_prev(layout._ref, ref)
        ## asign new ref to layout
        layout._ref = ref
        if new_path:
            layout._base_folder = os.path.join(self.base_folder, new_path)

    def assign_rrev(self, layout: ReferenceLayout, ref: ConanReference):
        assert ref.reference == layout._ref.reference, "You cannot change reference name here"
        assert ref.rrev, "It only makes sense to change if you are providing a revision"
        assert not ref.prev, "The reference for the recipe should not have package revision"
        assert not ref.pkgid, "The reference for the recipe should not have package id"

        # TODO: here maybe we should block the recipe and all the packages too
        old_ref = layout._ref
        layout._ref = ref

        # Move temporal folder contents to final folder
        new_path = self._move_rrev(old_ref, layout._ref)
        if new_path:
            layout._base_folder = os.path.join(self.base_folder, new_path)
