from conan.cache.package_layout import PackageLayout
from conans.model.ref import ConanFileReference
from conans.model.ref import PackageReference


class RecipeLayout:
    def __init__(self, cache: 'Cache', ref: ConanFileReference):
        self._cache = cache
        self._ref = ref

    def get_package_layout(self, pref: PackageReference) -> PackageLayout:
        assert pref.ref == self._ref
        return PackageLayout(self, pref)
