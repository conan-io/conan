from conan.cache.cache import Cache


class CacheTwoLevels:
    """
    Wrapper for a two-level cache implementation. Under the hood it instantiates two cache objects,
    one of them configured to be read-only. The read-only cache is a fallback for read operations
    while the other is the one for any write operation.
    """

    def __init__(self, workspace_cache: Cache, user_cache: Cache):
        self._workspace = workspace_cache
        self._user_cache = user_cache

