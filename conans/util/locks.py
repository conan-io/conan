import fasteners
from conans.util.log import logger
import time
from conans.util.files import save, load
import psutil
import os


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

    def __init__(self, folder, locked_item, output):
        self._count_file = folder + ".count"
        self._count_lock_file = folder + ".count.lock"
        self._locked_item = locked_item
        self._output = output
        self._first_lock = True

    def _info_locked(self):
        if self._first_lock:
            self._first_lock = False
            self._output.info("%s is locked by another concurrent conan process, wait..."
                              % str(self._locked_item))
            self._output.info("If not the case, quit, and do 'conan remove %s -f'"
                              % str(self._locked_item))

    def _pids(self):
        try:
            contents = load(self._count_file)
        except IOError:
            return []
        else:
            if not contents:
                return []
            pids = [int(i) for i in contents.split(',')]
            valid_pids = []
            for pid in pids:
                if not psutil.pid_exists(abs(pid)):
                    lock_type = "write" if pid < 0 else "read"
                    self._output.info("invalidate %s lock from PID %s" % (lock_type, abs(pid)))
                else:
                    valid_pids.append(pid)
            return valid_pids


class ReadLock(Lock):

    def _save_pids(self, pids):
        save(self._count_file, ','.join(str(pid) for pid in pids))

    def __enter__(self):
        while True:
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                pids = self._pids()
                if len(pids) >= 0:
                    pids.append(os.getpid())
                    save(self._count_file, ','.join(str(pid) for pid in pids))
                    break
            self._info_locked()
            time.sleep(READ_BUSY_DELAY)

    def __exit__(self, exc_type, exc_val, exc_tb):   # @UnusedVariable
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            pids = self._pids()
            try:
                pids.remove(os.getpid())
            except ValueError:
                # legal situation - conan may remove directory with lock file during write
                pass
            self._save_pids(pids)


class WriteLock(Lock):

    def __enter__(self):
        while True:
            with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
                pids = self._pids()
                if not pids:
                    save(self._count_file, "-%s" % os.getpid())
                    break
            self._info_locked()
            time.sleep(WRITE_BUSY_DELAY)

    def __exit__(self, exc_type, exc_val, exc_tb):  # @UnusedVariable
        with fasteners.InterProcessLock(self._count_lock_file, logger=logger):
            save(self._count_file, "")
