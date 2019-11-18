import unittest
import os.path
import tempfile

from conans.util import locks


class Deadlock(Exception):
    pass


class ProtoLock(object):
    def __init__(self):
        self._n_readers = 0
        self._has_writer = False

    def acquire(self):
        if not self.try_acquire():
            raise Deadlock()

    def try_acquire(self):
        if self.holds_lock():
            return False
        self._has_writer = True
        return True

    def acquire_shared(self):
        if not self.try_acquire_shared():
            raise Deadlock()

    def try_acquire_shared(self):
        if self._has_writer:
            return False
        self._n_readers += 1
        return True

    def release(self):
        assert self.holds_lock(), 'Double-release'
        self._has_writer = False

    def release_shared(self):
        assert self._n_readers > 0
        self._n_readers -= 1

    def holds_lock(self):
        return self._has_writer or self._n_readers != 0


class LockContextManagerTests(unittest.TestCase):
    def _do_lock(self, lk):
        with locks.hold_lock(lk):
            pass

    def _do_lock_shared(self, lk):
        with locks.hold_lock_shared(lk):
            pass

    def test_ctxman_exclusive(self):
        lk = ProtoLock()
        self.assertFalse(lk.holds_lock())
        with locks.hold_lock(lk):
            self.assertTrue(lk.holds_lock())
            # Another acquire() will block:
            self.assertRaises(Deadlock, lambda: self._do_lock(lk))
            self.assertRaises(Deadlock, lambda: self._do_lock_shared(lk))
            self.assertTrue(lk.holds_lock())
        # Context-exit unlocks:
        self.assertFalse(lk.holds_lock())

    def test_ctxman_shared(self):
        lk = ProtoLock()
        self.assertFalse(lk.holds_lock())
        with locks.hold_lock_shared(lk):
            self.assertTrue(lk.holds_lock())
            self._do_lock_shared(lk)
            self.assertTrue(lk.holds_lock())
        # Context-exit unlocks:
        self.assertFalse(lk.holds_lock())

    def test_ctxman_try_excl(self):
        lk = ProtoLock()
        self.assertFalse(lk.holds_lock())
        with locks.try_hold_lock(lk) as got_lock:
            # We get the lock
            self.assertTrue(got_lock)
            self.assertTrue(lk.holds_lock())
            # Trying to get another lock blocks
            self.assertRaises(Deadlock, lambda: self._do_lock(lk))
            self.assertRaises(Deadlock, lambda: self._do_lock_shared(lk))
            # Check nested contexts
            self.assertTrue(lk.holds_lock())
            with locks.try_hold_lock(lk) as got_lock_again:
                self.assertFalse(got_lock_again)
            # Failing to get a lock doesn't unlock it
            self.assertTrue(lk.holds_lock())
            with locks.try_hold_lock_shared(lk) as got_lock_again:
                self.assertFalse(got_lock_again)
            self.assertTrue(lk.holds_lock())
        # Context-exit unlocks:
        self.assertFalse(lk.holds_lock())

    def test_ctxman_try_shared(self):
        lk = ProtoLock()
        self.assertFalse(lk.holds_lock())
        with locks.try_hold_lock_shared(lk) as got_lock:
            self.assertTrue(got_lock)
            self.assertTrue(lk.holds_lock())
            # Trying to get exclusive locks blocks
            self.assertRaises(Deadlock, lambda: self._do_lock(lk))
            # But a shared lock is okay
            self._do_lock_shared(lk)
            # Nested context managers
            self.assertTrue(lk.holds_lock())
            with locks.try_hold_lock(lk) as got_lock_again:
                self.assertFalse(got_lock_again)
            self.assertTrue(lk.holds_lock())
            with locks.try_hold_lock_shared(lk) as got_lock_again:
                self.assertTrue(got_lock_again)
            self.assertTrue(lk.holds_lock())
        # Context-exit unlocks:
        self.assertFalse(lk.holds_lock())


class FileLockTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.lock_path = os.path.join(self.temp_dir, 'lock.txt')

    def tearDown(self):
        os.unlink(self.lock_path)
        os.rmdir(self.temp_dir)

    def test_acquire(self):
        lk = locks.FileLock(self.lock_path)
        lk.acquire()
        try:
            self.assertTrue(lk.holds_lock())
        finally:
            lk.release()
        self.assertFalse(lk.holds_lock())

    def test_acquire_shared(self):
        lk = locks.FileLock(self.lock_path)
        lk.acquire_shared()
        try:
            self.assertTrue(lk.holds_lock())
        finally:
            lk.release_shared()
        self.assertFalse(lk.holds_lock())
