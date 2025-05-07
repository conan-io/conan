""" The semaphore module provides inter-process locking mechanisms to ensure Conan commands can
    run concurrently without conflicts.

    It uses the fasteners library to create and manage locks across multiple processes. Thus, this
    module is a proxy in case the project need to use a different library in the future.

    A timeout is defined to prevent deadlocks, and the lock files are stored in a temporary directory
    in the conan cache folder. Still, the timeout is configured in seconds, using the configuration
    `core.cache.parallel:timeout` in the conan.conf file.
    The default value is 300 seconds (5 minutes).

    The fasteners have context managers, but only acquire() method has a timeout
    parameter, that's why we needed to extend sleep method to inject the timeout check.
"""
import functools
import os
import time
from datetime import datetime

from conan.errors import ConanException
from conan.api.output import ConanOutput
from conan.internal.cache.cache import PkgCache


CONAN_SEMAPHORE_TIMEOUT = 300.0  # 5 minutes
CONAN_SEMAPHORE_LOCKFILE = "conan_semaphore.lock"

def _acquire_timeout(cache_folder) -> float:
    """ Get the timeout value for acquiring locks.

    Imported ConanAPI locally to avoid circular import issues.

    :param cache_folder: Path to the Conan cache folder
    :return: Timeout value in seconds
    """
    from conan.api.subapi.config import ConfigAPI
    config = ConfigAPI.load_config(cache_folder)
    timeout = config.get("core.cache.parallel:timeout", default=CONAN_SEMAPHORE_TIMEOUT, check_type=float)
    return float(timeout)

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
            acquire_timeout = _acquire_timeout(conan_api.cache_folder)
            now = datetime.now()
            def _sleep_timeout(interval: float) -> None:
                time.sleep(interval)
                if (datetime.now() - now).total_seconds() > acquire_timeout:
                    raise ConanException(
                        f"Conan could not acquire interprocess-lock within {acquire_timeout} seconds"
                         " during parallel process execution. Please, update the conf"
                        " 'core.cache.parallel:timeout' in conan.conf file to a higher value."
                    )

            import fasteners
            lock = fasteners.InterProcessLock(path=_lockfile_path(conan_api),
                                              sleep_func=_sleep_timeout)
            ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring semaphore lock.")
            with lock:
                ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been locked.")
                return func(*args, **kwargs)
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been released.")
        return wrapper
    return decorator
