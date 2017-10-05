import fasteners
from conans.util.log import logger
import time
from conans.util.files import save, load


class NoLock(object):

    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        pass


class SimpleLock(object):

    def __init__(self, filename):
        self._lock = fasteners.InterProcessLock(filename, logger=logger)

    def __enter__(self):
        self._lock.acquire()

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        self._lock.release()


READ_BUSY_DELAY = 0.5
WRITE_BUSY_DELAY = 0.25


class Lock(object):

    def __init__(self, folder):
        self._count_file = folder + ".count"
        self._count_lock_file = folder + ".count.lock"

    def _readers(self):
        try:
            return int(load(self._count_file))
        except IOError:
            return 0


class ReadLock(Lock):

    def __enter__(self):
        while True:
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                readers = self._readers()
                if readers >= 0:
                    save(self._count_file, str(readers + 1))
                    break
            time.sleep(READ_BUSY_DELAY)

    def __exit__(self, exc_type, exc_val, exc_tb):   # @UnusedVariable
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            readers = self._readers()
            save(self._count_file, str(readers - 1))


class WriteLock(Lock):

    def __enter__(self):
        while True:
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                readers = self._readers()
                if readers == 0:
                    save(self._count_file, "-1")
                    break
            time.sleep(WRITE_BUSY_DELAY)

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            save(self._count_file, "0")
