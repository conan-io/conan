"""
Implements locking utilities, including filesystem-based OS-assisted
shared/exclusive advisory locking.
"""

import ctypes
import errno
import os
from contextlib import contextmanager


class NoLock(object):
    """
    A context manager that does nothing on enter/exit. Used to represent locks
    that have been disabled.
    """

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        pass


class FileLock(object):
    """
    Implements OS-supported shared and exclusive locking using the native
    platform APIs. No matter how the process is terminated, the system will
    ensure that the locks are released.

    :param filepath: The path to the file that represents the lock
    """
    def __init__(self, filepath):
        #: The path to the file which is used as a lock.
        self.filepath = filepath
        self._file = None
        self._native_fd = None
        self._holds_lock = False
        if os.name == 'nt':
            self._acquire_method = self._acquire_nt
            self._release_method = self._release_nt
        else:
            self._acquire_method = self._acquire_unix
            self._release_method = self._release_unix

    def _acquire_unix(self, exclusive, block):
        # Obtain a new file descriptor
        assert self._native_fd is None, 'FileLock() cannot be used recursively'
        assert self._file is None
        self._file = open(self.filepath, 'wb+')
        self._native_fd = self._file.fileno()
        # Build the flags
        import fcntl
        lk_flags = fcntl.LOCK_EX if exclusive else fcntl.LOCK_SH
        if not block:
            lk_flags |= fcntl.LOCK_NB
        # Take the lock
        try:
            n_bytes = 1
            fcntl.lockf(self._native_fd, lk_flags, n_bytes)
        except OSError as exc:
            if exc.errno in (errno.EAGAIN, errno.EACCES):
                # Failed to take the lock. Never reached when block=True
                return False
            # Some other exception...
            raise
        # Got it!
        self._holds_lock = True
        return True

    def _release_unix(self):
        assert self._native_fd is not None, 'Cannot release() a lock that is not held'
        assert self._file is not None
        import fcntl
        fcntl.lockf(self._native_fd, fcntl.LOCK_UN)
        self._holds_lock = False
        self._native_fd = None
        self._file.close()
        self._file = None

    def _acquire_nt(self, exclusive, block):
        self._file = open(self.filepath, 'wb+')
        self._native_fd = self._file.fileno()

        from . import win32_lockapi

        flags = 0
        if exclusive:
            flags |= win32_lockapi.LOCKFILE_EXCLUSIVE_LOCK
        if not block:
            flags |= win32_lockapi.LOCKFILE_FAIL_IMMEDIATELY

        okay = win32_lockapi.LockFileEx(
            win32_lockapi.get_win_handle(self._file),
            flags,
            0,
            0,
            0,
            ctypes.pointer(win32_lockapi.OVERLAPPED()),
        )
        if not okay:
            last_error = win32_lockapi.GetLastError()
            if last_error != win32_lockapi.ERROR_IO_PENDING:
                raise OSError(last_error)
            return False
        self._holds_lock = True
        return True

    def _release_nt(self):
        assert self._native_fd is not None, 'Cannot release() a lock that is not held'
        from . import win32_lockapi
        okay = win32_lockapi.UnlockFileEx(
            win32_lockapi.get_win_handle(self._native_fd),
            0,
            0,
            0,
            ctypes.pointer(win32_lockapi.OVERLAPPED()),
        )
        if not okay:
            raise OSError(win32_lockapi.GetLastError())

        self._holds_lock = False
        self._native_fd = None
        self._file.close()
        self._file = None

    def try_acquire_shared(self):
        """
        Try to acquire shared ownership. Returns ``bool`` of whether the lock
        was successfully obtained.
        """
        return self._acquire_method(exclusive=False, block=False)

    def try_acquire(self):
        """
        Try to acquire exclusive ownership. Returns ``bool`` of whether the
        lock was successfully obtained.
        """
        return self._acquire_method(exclusive=True, block=False)

    def acquire_shared(self):
        """
        Acquire shared ownership. Blocks until ownership can be obtained.
        """
        self._acquire_method(exclusive=False, block=True)

    def acquire(self):
        """
        Acquire exclusive ownership. Blocks until ownership can be obtained.
        """
        self._acquire_method(exclusive=True, block=True)

    def release_shared(self):
        """
        Release shared ownership of the resource.
        """
        self._release_method()

    def release(self):
        """
        Release exclusive ownership of the resource.
        """
        self._release_method()

    def holds_lock(self):
        """
        Determine if a lock is currently held.
        """
        return self._holds_lock


@contextmanager
def hold_lock(lk):
    """
    Context manager which holds exclusive ownership over the given lockable
    object ``lk``. Requires ``.acquire()`` and ``.release()`` methods on ``lk``.
    """
    lk.acquire()
    try:
        yield
    finally:
        lk.release()


@contextmanager
def hold_lock_shared(lk):
    """
    Context manager which holds shared ownership over the given lockable object
    ``lk``. Requires ``.acquire_shared()`` and ``.release_shared()`` methods on
    ``lk``.
    """
    lk.acquire_shared()
    try:
        yield
    finally:
        lk.release_shared()


@contextmanager
def try_hold_lock(lk):
    """
    Context manager which tries to obtain exclusive ownership over the lock.
    Yields a ``bool`` of whether the lock was obtained. Requires
    ``.try_acquire()`` and ``.release()`` methods on ``lk``.
    """
    got_lock = lk.try_acquire()
    try:
        yield got_lock
    finally:
        if got_lock:
            lk.release()


@contextmanager
def try_hold_lock_shared(lk):
    """
    Context manager which tries to obtain shared ownership over the lock.
    Yields a ``bool`` of whether the lock was obtained. Requires
    ``.try_acquire_shared()`` and ``.release_shared()`` methods on ``lk``.
    """
    got_lock = lk.try_acquire_shared()
    try:
        yield got_lock
    finally:
        if got_lock:
            lk.release_shared()
