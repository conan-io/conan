import os
import uuid
from contextlib import contextmanager, ExitStack
from typing import List

from conan.cache.cache import Cache
from conan.cache.cache_folder import CacheFolder
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout(LockableMixin):

    def __init__(self, ref: ConanFileReference, cache: Cache, base_folder: str, locked=True, **kwargs):
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

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        assert str(pref.ref) == str(self._ref), "Only for the same reference"
        assert not self._random_rrev, "When requesting a package, the rrev is already known"
        assert self._ref.revision == pref.ref.revision, "Ensure revision is the same"
        from conan.cache.package_layout import PackageLayout
        layout = PackageLayout(self, pref, cache=self._cache, manager=self._manager)
        self._package_layouts.append(layout)  # TODO: Not good, persists even if it is not used
        return layout

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):  # TODO: Decide if we want to wait by default
        # I need the same level of blocking for all the packages
        # TODO: Here we don't want to block all MY package_layouts, but ALL existings
        with ExitStack() as stack:
            if blocking:
                for package_layout in self._package_layouts:
                    stack.enter_context(package_layout.lock(blocking, wait))
            stack.enter_context(super().lock(blocking, wait))
            yield

    # These folders always return a final location (random) inside the cache.
    @property
    def base_directory(self):
        with self.lock(blocking=False):
            return os.path.join(self._cache.base_folder, self._base_folder)

    def export(self):
        export_directory = lambda: os.path.join(self.base_directory, 'export')
        return CacheFolder(export_directory, False, manager=self._manager, resource=self._resource)

    def export_sources(self):
        export_sources_directory = lambda: os.path.join(self.base_directory, 'export_sources')
        return CacheFolder(export_sources_directory, False, manager=self._manager,
                           resource=self._resource)

    def source(self):
        source_directory = lambda: os.path.join(self.base_directory, 'source')
        return CacheFolder(source_directory, False, manager=self._manager, resource=self._resource)
