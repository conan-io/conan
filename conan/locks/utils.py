from contextlib import contextmanager

from conan.locks.lockable_mixin import LockableMixin


@contextmanager
def try_write_else_read_wait(lockable: LockableMixin) -> bool:
    """ It wants a write lock over a resource, but if it is already in use then it wants a
        read lock. Return value informs whether the lock adquired is a blocking one or not.
    """
    try:
        with lockable.lock(blocking=True, wait=False):
            yield True
    except Exception as e:
        # If we cannot get an exclusive lock, then we want a shared lock to read.
        # FIXME: We are assuming it fails because of the wait=False
        with lockable.lock(blocking=False, wait=True):
            yield False
