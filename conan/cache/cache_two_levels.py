from io import StringIO

from conan.cache.cache import Cache
from conan.cache.cache_implementation import CacheImplementation
from model.ref import PackageReference, ConanFileReference


class CacheTwoLevels(Cache):
    """
    Wrapper for a two-level cache implementation. Under the hood it instantiates two cache objects,
    one of them configured to be read-only. The read-only cache is a fallback for read operations
    while the other is the one for any write operation.
    """
    def __init__(self, workspace_cache: CacheImplementation, user_cache: CacheImplementation):
        self._workspace = workspace_cache
        self._user_cache = user_cache

    def dump(self, output: StringIO):
        pass

    def get_reference_layout(self, ref: ConanFileReference) -> 'RecipeLayout':
        pass

    def get_package_layout(self, pref: PackageReference) -> 'PackageLayout':
        pass


