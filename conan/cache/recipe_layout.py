import os
from contextlib import contextmanager, ExitStack

from conan.cache.cache import DataCache
from conan.cache.conan_reference import ConanReference
from conan.locks.lockable_mixin import LockableMixin
from conans.errors import RecipeNotFoundException
from conans.model.package_metadata import PackageMetadata
from conans.model.ref import ConanFileReference
from conans.paths import PACKAGE_METADATA, CONANFILE, SCM_SRC_FOLDER
from conans.util.files import load


class RecipeLayout(LockableMixin):

    def __init__(self, ref: ConanReference, cache: DataCache, base_folder: str,
                 locked=True,
                 **kwargs):
        self._ref = ref
        self._cache = cache
        self._locked = locked
        self._base_folder = base_folder
        super().__init__(resource=self._ref.full_reference, **kwargs)

    def assign_rrev(self, ref: ConanReference, move_contents: bool = False):
        assert not self._locked, "You can only change it if it was not assigned at the beginning"
        assert str(ref.full_reference) == str(self._ref.full_reference), "You cannot change the reference here"
        assert ref.revision, "It only makes sense to change if you are providing a revision"
        new_resource: str = ref.full_str()

        # Block the recipe and all the packages too
        with self.exchange(new_resource):
            # Assign the new revision
            old_ref = self._ref
            self._ref = ref
            self._locked = True

            # Reassign folder in the database (only the recipe-folders)
            new_path = self._cache._move_rrev(old_ref, self._ref, move_contents)
            if new_path:
                self._base_folder = new_path

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):  # TODO: Decide if we want to wait by default
        # I need the same level of blocking for all the packages
        with ExitStack() as stack:
            if blocking:
                for pref in list(self._cache.db.list_package_references(self._ref)):
                    layout = self._cache.get_package_layout(pref)
                    stack.enter_context(layout.lock(blocking, wait))
                    # TODO: Fix somewhere else: cannot get a new package-layout for a reference that is blocked.
            stack.enter_context(super().lock(blocking, wait))
            yield

    # These folders always return a final location (random) inside the cache.
    @property
    def base_directory(self):
        with self.lock(blocking=False):
            return os.path.join(self._cache.base_folder, self._base_folder)

    def export(self):
        return os.path.join(self.base_directory, 'export')

    def export_sources(self):
        return os.path.join(self.base_directory, 'export_sources')

    def source(self):
        return os.path.join(self.base_directory, 'source')

    # TODO: cache2.0: Do we want this method?
    def conanfile(self):
        return os.path.join(self.export(), CONANFILE)

    # TODO: cache2.0: Do we want this method?
    def scm_sources(self):
        return os.path.join(self.base_directory, SCM_SRC_FOLDER)
