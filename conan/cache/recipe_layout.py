import os
from contextlib import contextmanager, ExitStack

from conan.cache.cache_folder import CacheFolder
from conan.cache.package_layout import PackageLayout
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout(LockableMixin):
    def __init__(self, ref: ConanFileReference, cache: 'Cache', **kwargs):
        super().__init__(**kwargs)
        self._ref = ref
        self._cache = cache  # We need the cache object to notify about folders that are moved
        self._package_layouts = []
        self._base_directory = None

    def get_package_layout(self, pref: PackageReference) -> PackageLayout:
        assert pref.ref == self._ref
        unique_id = f'{self._resource}:{pref.package_id}#{pref.revision}'
        layout = PackageLayout(self, unique_id=unique_id, pref=pref, locks_manager=self._manager)
        self._package_layouts.append(layout)  # TODO: Not good, persists even if it is not used

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):  # TODO: Decide if we want to wait by default
        # I need the same level of blocking for all the packages
        with ExitStack() as stack:
            for package_layout in self._package_layouts:
                stack.enter_context(package_layout(blocking, wait))

        with super().lock(blocking, wait):
            yield

    # These folders always return a final location (random) inside the cache.
    def export(self):
        export_directory = os.path.join(self._base_directory, 'export')
        return CacheFolder(export_directory, False, manager=self._manager, resource=self._resource)

    def export_sources(self):
        export_directory = os.path.join(self._base_directory, 'export_sources')
        return CacheFolder(export_directory, False, manager=self._manager, resource=self._resource)

    def source(self):
        export_directory = os.path.join(self._base_directory, 'source')
        return CacheFolder(export_directory, False, manager=self._manager, resource=self._resource)
