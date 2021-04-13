import os
from contextlib import contextmanager, ExitStack

from conan.cache.cache_implementation import CacheImplementation
from conan.cache.package_layout import PackageLayout
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout(LockableMixin):

    def __init__(self, ref: ConanFileReference, cache: CacheImplementation, base_folder: str,
                 locked=True,
                 **kwargs):
        self._ref = ref
        self._cache = cache
        self._locked = locked
        self._base_folder = base_folder
        super().__init__(resource=self._ref.full_str(), **kwargs)

    def assign_rrev(self, ref: ConanFileReference, move_contents: bool = False):
        assert not self._locked, "You can only change it if it was not assigned at the beginning"
        assert str(ref) == str(self._ref), "You cannot change the reference here"
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

    def get_package_layout(self, pref: PackageReference) -> PackageLayout:
        """
        Returns the package_layout for the given 'pref' in the SAME CACHE where this recipe_layout
        is stored. If the package doesn't already exists it is created.
        """
        # TODO: Alternatively we can add a 'get_or_create_package_layout' method
        assert str(pref.ref) == str(self._ref), "Only for the same reference"
        assert self._locked, "Before requesting a package, assign the rrev using 'assign_rrev'"
        assert self._ref.revision == pref.ref.revision, "Ensure revision is the same"
        return self._get_package_layout(pref)

    def _get_package_layout(self, pref: PackageReference) -> PackageLayout:
        if pref.revision:
            return self._cache.get_package_layout(pref)
        else:
            pkg_layout, _ = self._cache.get_or_create_package_layout(pref)
            return pkg_layout

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
