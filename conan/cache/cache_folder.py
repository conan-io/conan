import os

from conan.locks.lockable_mixin import LockableMixin


class CacheFolder(LockableMixin):

    def __init__(self, directory: str, movible=False, **kwargs):
        super().__init__(**kwargs)
        self._directory = directory
        self._movible = movible

    def __str__(self) -> str:
        # Best we can do is to block before returning just in case the directory is being moved...
        # although we cannot ensure the returned value will be valid after it.
        with self.lock(blocking=False):
            return self._directory

    def move(self, new_location: str):
        """ It will move all the contents to the new location """
        assert self._movible, 'This folder is not movible, sorry for you Conan developer.'
        with self.lock(blocking=True):
            os.rename(self._directory, new_location)
            self._directory = new_location

            # TODO: If we maintain an entry in the database in order to do some LRU, we need to
            # TODO: update database entry.
