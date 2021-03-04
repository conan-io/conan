from contextlib import contextmanager
from typing import Tuple

from conan.cache._tables.packages import Packages
from conan.cache._tables.references import References
from conan.cache.cache_implementation import CacheImplementation
from conan.cache.exceptions import ReadOnlyCache
from conan.cache.package_layout import PackageLayout
from conan.cache.recipe_layout import RecipeLayout
from model.ref import ConanFileReference, PackageReference


class RecipeLayoutReadOnly(RecipeLayout):
    """ Prevents creation of new packages """

    def __init__(self, ref, locked=True, *args, **kwargs):
        assert ref.revision, 'A read-only recipe layout is always initialized with a know rrev'
        assert locked, 'It is not possible to modify the rrev of a read-only recipe layout'
        super().__init__(ref=ref, locked=True, *args, **kwargs)

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):
        if blocking:
            raise ReadOnlyCache('Cannot block to write a read-only recipe layout')

        with super().lock(blocking=False, wait=wait):
            yield


class CacheImplementationReadOnly(CacheImplementation):
    """ An implementation that prevents adding new references or packages """

    def _get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        reference_path = self.db.try_get_reference_directory(ref)
        return RecipeLayoutReadOnly(ref, cache=self, manager=self._locks_manager,
                                    base_folder=reference_path)

    def get_or_create_reference_layout(self, ref: ConanFileReference) -> Tuple[RecipeLayout, bool]:
        if ref.revision:
            try:
                return self.get_reference_layout(ref), False
            except References.DoesNotExist:
                pass
        raise ReadOnlyCache('Cannot create new references in a read-only cache')

    def get_or_create_package_layout(self, pref: PackageReference) -> Tuple[PackageLayout, bool]:
        if pref.revision:
            try:
                return self.get_package_layout(pref)
            except Packages.DoesNotExist:
                pass
        raise ReadOnlyCache('Cannot create packages using a read-only recipe layout')
