import os

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
from conans.errors import ConanException
from conans.model.manifest import FileTreeManifest
from conans.paths import CONANFILE, SCM_SRC_FOLDER


# TODO: cache2.0 create an unique layout class
from conans.util.files import rmdir


class RecipeLayout:

    def __init__(self, ref: ConanReference, cache: DataCache, base_folder: str):
        self._ref = ref
        self._cache = cache
        self._base_folder = base_folder

    @property
    def reference(self):
        return self._ref.as_conanfile_reference()

    def assign_rrev(self, ref: ConanReference, remote=None):
        assert ref.reference == self._ref.reference, "You cannot change reference name here"
        assert ref.rrev, "It only makes sense to change if you are providing a revision"
        # TODO: here maybe we should block the recipe and all the packages too
        # Assign the new revision
        old_ref = self._ref
        self._ref = ref

        # Move temporal folder contents to final folder
        new_path = self._cache._move_rrev(old_ref, self._ref, remote=remote)
        if new_path:
            self._base_folder = new_path

    # These folders always return a final location (random) inside the cache.
    @property
    def base_directory(self):
        return os.path.join(self._cache.base_folder, self._base_folder)

    def export(self):
        return os.path.join(self.base_directory, 'export')

    def export_sources(self):
        return os.path.join(self.base_directory, 'export_sources')

    def download_export(self):
        return os.path.join(self.base_directory, "dl", "export")

    def source(self):
        return os.path.join(self.base_directory, 'source')

    # TODO: cache2.0: Do we want this method?
    def conanfile(self):
        return os.path.join(self.export(), CONANFILE)

    # TODO: cache2.0: Do we want this method?
    def scm_sources(self):
        return os.path.join(self.base_directory, SCM_SRC_FOLDER)

    def recipe_manifest(self):
        return FileTreeManifest.load(self.export())

    def get_remote(self):
        return self._cache.get_remote(self._ref)

    def remove(self):
        try:
            rmdir(self.base_directory)
            self._cache.remove(self._ref)
        except OSError as e:
            raise ConanException(f"Couldn't remove folder {self.base_directory}: {str(e)}")
