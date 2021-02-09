import os
from typing import Callable

from conan.locks.lockable_mixin import LockableMixin


class CacheFolder(LockableMixin):

    def __init__(self, directory: Callable[[], str], movible=False, **kwargs):
        super().__init__(**kwargs)
        self._directory = directory
        self._movible = movible

    def __str__(self) -> str:
        return self._directory()

    def move(self, new_location: str):
        """ It will move all the contents to the new location """
        assert self._movible, 'This folder is not movible, sorry for you Conan developer.'
        with self.lock(blocking=True):
            os.rename(self._directory, new_location)
            self._directory = new_location

            # TODO: If we maintain an entry in the database in order to do some LRU, we need to
            # TODO: update database entry.
