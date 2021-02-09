import os
from contextlib import contextmanager, ExitStack

from conan.cache.cache_folder import CacheFolder
from conan.cache.package_layout import PackageLayout
from conan.locks.lockable_mixin import LockableMixin
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout(LockableMixin):
    def __init__(self, ref: ConanFileReference, base_directory: str, cache: 'Cache', **kwargs):
        self._ref = ref
        self._cache = cache  # We need the cache object to notify about folders that are moved
        self._base_directory = base_directory
        self._package_layouts = []
        resource_id = ref.full_str()
        super().__init__(resource=resource_id, **kwargs)

    def get_package_layout(self, pref: PackageReference) -> PackageLayout:
        assert pref.ref == self._ref

        package_path = self._cache._backend.get_directory(self._ref, pref)  # TODO: Merge classes Cache and CacheDatabase? Probably the backend is just the database, not the logic.
        base_package_directory = os.path.join(self._cache.base_folder, package_path)
        layout = PackageLayout(self, pref, base_package_directory, cache=self._cache, manager=self._manager)
        # RecipeLayout(ref, base_reference_directory, cache=self, manager=self._locks_manager)
        self._package_layouts.append(layout)  # TODO: Not good, persists even if it is not used
        return layout

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
        export_sources_directory = os.path.join(self._base_directory, 'export_sources')
        return CacheFolder(export_sources_directory, False, manager=self._manager, resource=self._resource)

    def source(self):
        source_directory = os.path.join(self._base_directory, 'source')
        return CacheFolder(source_directory, False, manager=self._manager, resource=self._resource)
