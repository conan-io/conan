import functools
import os
import tempfile
import fasteners
from datetime import datetime

from conan.errors import ConanException
from conan.api.output import ConanOutput


def process_lock(timeout=300.0):
    """Execute inter-process lock to avoid concurrency when running multiple instances of Conan
    client at same time.

    The lock is done by fastener, that uses fcntl or msvcrt to mark conan.lock as locked.

    This decorator is equipped with a timeout, defaulted to 5 min, in order to avoid breaking large
    downloads. In case a timeout occurs, a ConanException is raised.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            lockfile = os.path.join(tempfile.gettempdir(), "conan.lock")
            lock = fasteners.InterProcessLock(lockfile)
            pid = os.getpid()
            now = datetime.now()
            ConanOutput().debug(f"{now} [{pid}]: Getting lock.")
            acquired = lock.acquire(timeout=timeout)
            if not acquired:
                raise ConanException(f"Conan could not acquire lock within {timeout} seconds during"
                                      " parallel process execution.")
            try:
                ConanOutput().debug(f"{now} [{pid}]: Locked.")
                return func(self, *args, **kwargs)
            finally:
                if acquired:
                    ConanOutput().debug(f"{now} [{pid}]: Released.")
                    lock.release()
        return wrapper
    return decorator
