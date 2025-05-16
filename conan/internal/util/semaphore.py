""" The semaphore module provides inter-process locking mechanisms to ensure Conan commands can
    run concurrently without conflicts.

    It uses the fasteners library to create and manage locks across multiple processes. Thus, this
    module is a proxy in case the project need to use a different library in the future.
"""
import functools
import os
import time
from datetime import datetime

from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.internal.cache.cache import PkgCache


CONAN_SEMAPHORE_LOCKFILE = "conan_semaphore.lock"


def _lockfile_path(conan_api) -> str:
    """ Get the path to the interprocess lock file.

    :param conan_api: ConanAPI instance
    :return: Path to the lock file in Conan cache temporary directory
    """
    cache = PkgCache(conan_api.cache_folder, conan_api.config.global_conf)
    return os.path.join(cache.temp_folder, CONAN_SEMAPHORE_LOCKFILE)

def interprocess_lock():
    """ Decorator to acquire an interprocess lock for a function.

        This method uses the fasteners library to create an interprocess lock, and serves as a proxy
        for the library. The lock is acquired using the InterProcessLock class, which allows multiple
        processes to safely access shared resources. The lock is released automatically when the
        decorated function completes.

        The timeout is injected in the sleep method of the InterProcessLock class, otherwise it would
        require an extra code to manage acquire() and release() calls.

        The ConanAPI is imported locally to avoid circular import issues.
    """
    def decorator(func):
        pid = os.getpid()
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from conan.api.conan_api import ConanAPI
            conan_api = ConanAPI()
            import fasteners
            lock = fasteners.InterProcessLock(path=_lockfile_path(conan_api))
            ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring semaphore lock.")
            with lock:
                ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been locked.")
                return func(*args, **kwargs)
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been released.")
        return wrapper
    return decorator


def interprocess_write_lock():
    """ Decorator to acquire an interprocess write lock for a function.

        This method uses the fasteners library to create an interprocess write lock.
        Unlike the interprocess_lock, it prevents other writers from acquiring the lock at same time,
        but allows multiple readers to access the shared resource concurrently.
    """
    def decorator(func):
        pid = os.getpid()
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from conan.api.conan_api import ConanAPI
            conan_api = ConanAPI()
            import fasteners
            lock = fasteners.InterProcessReaderWriterLock(path=_lockfile_path(conan_api))
            ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring write semaphore lock.")
            with lock.write_lock():
                ConanOutput().debug(f"{datetime.now()} [{pid}]: Write semaphore has been locked.")
                return func(*args, **kwargs)
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Write semaphore has been released.")
        return wrapper
    return decorator


def interprocess_read_lock():
    """ Decorator to acquire an interprocess read lock for a function.

        This method uses the fasteners library to create an interprocess read lock, and serves
        as a proxy for the fasteners library. It should be used with interprocess_write_lock to allow
        multiple processes to safely access shared resources.
    """
    def decorator(func):
        pid = os.getpid()
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            from conan.api.conan_api import ConanAPI
            conan_api = ConanAPI()
            import fasteners
            lock = fasteners.InterProcessReaderWriterLock(path=_lockfile_path(conan_api))
            ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring read semaphore lock.")
            with lock.read_lock():
                ConanOutput().debug(f"{datetime.now()} [{pid}]: Read semaphore has been locked.")
                return func(*args, **kwargs)
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Read semaphore has been released.")
        return wrapper
    return decorator
