from contextlib import contextmanager

from conan.locks.locks_manager import LocksManager


class LockableMixin:

    def __init__(self, manager: LocksManager, resource: str):
        self._manager = manager
        self._resource = resource

    @contextmanager
    def lock(self, blocking: bool, wait: bool = True):
        # TODO: Decide if this wait=True by default is what we want
        with self._manager.lock(self._resource, blocking, wait):
            yield
