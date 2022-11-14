import hashlib
import os

from conan.internal.cache.conan_reference_layout import RecipeLayout, PackageLayout
# TODO: Random folders are no longer accessible, how to get rid of them asap?
# TODO: Add timestamp for LRU
# TODO: We need the workflow to remove existing references.
from conan.internal.cache.db.cache_database import CacheDatabase
from conans.errors import ConanReferenceAlreadyExistsInDB, ConanReferenceDoesNotExistInDB
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.dates import revision_timestamp_now
from conans.util.files import rmdir, renamedir


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
    def _get_tmp_path(ref):
        # The reference will not have revision, but it will be always constant
        h = DataCache._short_hash_path(ref.repr_notime())
        return os.path.join("tmp", h)

    @staticmethod
    def _get_path(ref):
        return DataCache._short_hash_path(ref.repr_notime())

    def create_export_recipe_layout(self, ref: RecipeReference):
        # This is a temporary layout while exporting a new recipe, because the revision is not
        # computed yet, until it is. The entry is not added to DB, just a temp folder is created
        assert ref.revision is None, "Recipe revision should be None"
        assert ref.timestamp is None
        reference_path = self._get_tmp_path(ref)
        self._create_path(reference_path)
        return RecipeLayout(ref, os.path.join(self.base_folder, reference_path))

    def create_build_pkg_layout(self, pref: PkgReference):
        # Temporary layout to build a new package, when we don't know the package revision yet
        assert pref.ref.revision, "Recipe revision must be known to get or create the package layout"
        assert pref.package_id, "Package id must be known to get or create the package layout"
        assert pref.revision is None, "Package revision should be None"
        assert pref.timestamp is None
        package_path = self._get_tmp_path(pref)
        self._create_path(package_path)
        return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def get_reference_layout(self, ref: RecipeReference):
        """ the revision must exists, the folder must exist
        """
        assert ref.revision, "Recipe revision must be known to get the reference layout"
        ref_data = self._db.try_get_recipe(ref)
        ref_path = ref_data.get("path")
        return RecipeLayout(ref, os.path.join(self.base_folder, ref_path))

    def get_package_layout(self, pref: PkgReference):
        """ the revision must exists, the folder must exist
        """
        assert pref.ref.revision, "Recipe revision must be known to get the package layout"
        assert pref.package_id, "Package id must be known to get the package layout"
        assert pref.revision, "Package revision must be known to get the package layout"
        pref_data = self._db.try_get_package(pref)
        pref_path = pref_data.get("path")
        return PackageLayout(pref, os.path.join(self.base_folder, pref_path))

    def get_or_create_ref_layout(self, ref: RecipeReference):
        """ called by RemoteManager.get_recipe()
        """
        try:
            return self.get_reference_layout(ref)
        except ConanReferenceDoesNotExistInDB:
            assert ref.revision, "Recipe revision must be known to create the package layout"
            reference_path = self._get_path(ref)
            self._db.create_recipe(reference_path, ref)
            self._create_path(reference_path, remove_contents=False)
            return RecipeLayout(ref, os.path.join(self.base_folder, reference_path))

    def get_or_create_pkg_layout(self, pref: PkgReference):
        """ called by RemoteManager.get_package() and  BinaryInstaller
        """
        try:
            return self.get_package_layout(pref)
        except ConanReferenceDoesNotExistInDB:
            assert pref.ref.revision, "Recipe revision must be known to create the package layout"
            assert pref.package_id, "Package id must be known to create the package layout"
            assert pref.revision, "Package revision should be known to create the package layout"
            package_path = self._get_path(pref)
            self._db.create_package(package_path, pref, None)
            self._create_path(package_path, remove_contents=False)
            return PackageLayout(pref, os.path.join(self.base_folder, package_path))

    def update_recipe_timestamp(self, ref: RecipeReference):
        assert ref.revision
        assert ref.timestamp
        self._db.update_recipe_timestamp(ref)

    def list_references(self):
        return self._db.list_references()

    def exists_rrev(self, ref):
        return self._db.exists_rrev(ref)

    def exists_prev(self, pref):
        return self._db.exists_prev(pref)

    def get_latest_recipe_reference(self, ref):
        return self._db.get_latest_recipe_reference(ref)

    def get_latest_package_reference(self, pref):
        return self._db.get_latest_package_reference(pref)

    def get_recipe_revisions_references(self, ref: RecipeReference, only_latest_rrev=False):
        return self._db.get_recipe_revisions_references(ref, only_latest_rrev)

    def get_package_references(self, ref: RecipeReference, only_latest_prev=True):
        return self._db.get_package_references(ref, only_latest_prev)

    def get_package_revisions_references(self, pref: PkgReference, only_latest_prev=False):
        return self._db.get_package_revisions_references(pref, only_latest_prev)

    def get_matching_build_id(self, ref, build_id):
        return self._db.get_matching_build_id(ref, build_id)

    def get_recipe_timestamp(self, ref):
        return self._db.get_recipe_timestamp(ref)

    def get_package_timestamp(self, pref):
        return self._db.get_package_timestamp(pref)

    def remove_recipe(self, layout: RecipeLayout):
        layout.remove()
        self._db.remove_recipe(layout.reference)

    def remove_package(self, layout: RecipeLayout):
        layout.remove()
        self._db.remove_package(layout.reference)

    def assign_prev(self, layout: PackageLayout):
        pref = layout.reference

        new_path = self._get_path(pref)

        full_path = self._full_path(new_path)
        rmdir(full_path)

        renamedir(self._full_path(layout.base_folder), full_path)
        layout._base_folder = os.path.join(self.base_folder, new_path)

        build_id = layout.build_id
        pref.timestamp = revision_timestamp_now()
        # Wait until it finish to really update the DB
        try:
            self._db.create_package(new_path, pref, build_id)
        except ConanReferenceAlreadyExistsInDB:
            # This was exported before, making it latest again, update timestamp
            self._db.update_package_timestamp(pref)

        return new_path

    def assign_rrev(self, layout: RecipeLayout):
        """ called at export, once the exported recipe revision has been computed, it
        can register for the first time the new RecipeReference"""
        ref = layout.reference
        assert ref.revision is not None, "Revision must exist after export"
        assert ref.timestamp is None, "Timestamp no defined yet"
        ref.timestamp = revision_timestamp_now()

        # TODO: here maybe we should block the recipe and all the packages too
        # This is the destination path for the temporary created export and export_sources folders
        # with the hash created based on the recipe revision
        new_path_relative = self._get_path(ref)

        new_path_absolute = self._full_path(new_path_relative)

        if os.path.exists(new_path_absolute):
            # If there source folder exists, export and export_sources
            # folders are already copied so we can remove the tmp ones
            rmdir(self._full_path(layout.base_folder))
        else:
            # Destination folder is empty, move all the tmp contents
            renamedir(self._full_path(layout.base_folder), new_path_absolute)

        layout._base_folder = os.path.join(self.base_folder, new_path_relative)

        # Wait until it finish to really update the DB
        try:
            self._db.create_recipe(new_path_relative, ref)
        except ConanReferenceAlreadyExistsInDB:
            # This was exported before, making it latest again, update timestamp
            ref = layout.reference
            self._db.update_recipe_timestamp(ref)
