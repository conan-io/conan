""" The semaphore module provides inter-process locking mechanisms to ensure Conan commands can
    run concurrently without conflicts.

    It uses the fasteners library to create and manage locks across multiple processes. Thus, this
    module is a proxy in case the project need to use a different library in the future.
"""
import os
from datetime import datetime
from typing import Any
import inspect
import traceback

import fasteners

from conan.errors import ConanException
from conan.api.output import ConanOutput
from contextlib import contextmanager
from conan.internal.cache.cache import PkgCache


CONAN_SEMAPHORE_FILELOCK = "conan_semaphore.lock"


def _filelock_path(conan_api: Any) -> str:
    """ Get the path to the interprocess file lock.

    :param cache_folder: ConanAPI cache folder path
    :return: Path to the file lock in Conan cache temporary directory
    """
    cache = PkgCache(conan_api.cache_folder, conan_api._api_helpers.global_conf)
    return os.path.join(cache.filelock_folder, CONAN_SEMAPHORE_FILELOCK)


def _raised_by_fasteners(exc: BaseException) -> bool:
    """
    Check if the exception was raised by the fasteners library.

    :param exc: The exception to check.
    :return: True if the exception was raised by fasteners, False otherwise.
    """
    for frame, _ in traceback.walk_tb(exc.__traceback__):
        mod = inspect.getmodule(frame.f_code)
        if mod and (mod is fasteners or (getattr(mod, '__name__', '').startswith('fasteners'))):
            return True
    return False


@contextmanager
def interprocess_lock(conan_api: Any) -> None:
    """ Context manager to acquire an interprocess lock.

        This method uses the fasteners library to create an interprocess lock, and serves as a proxy
        for the library. The lock is acquired using the InterProcessLock class, which allows multiple
        processes to safely access shared resources. The lock is released automatically when the
        context manager exits.

    :param conan_api: ConanAPI instance
    :return: None
    """
    filelock_path = _filelock_path(conan_api)
    lock = fasteners.InterProcessLock(filelock_path)
    pid = os.getpid()
    try:
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring semaphore lock.")
        lock.acquire()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been locked.")
        yield
    except Exception as error:
        if _raised_by_fasteners(error):
            raise ConanException(f"Failed to acquire interprocess lock: {error}")
        else:
            raise
    finally:
        lock.release()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore has been released.")


@contextmanager
def interprocess_write_lock(conan_api: Any) -> None:
    """ Context manager to acquire an interprocess write lock.

        This method uses the fasteners library to create an interprocess write lock, and serves as a
        proxy for the library. The lock is acquired using the InterProcessReaderWriterLock class,
        which allows multiple processes to safely access shared resources. The lock is released
        automatically when the context manager exits.

    :param conan_api: ConanAPI instance
    :return: None
    """
    filelock_path = _filelock_path(conan_api)
    lock = fasteners.InterProcessReaderWriterLock(filelock_path)
    pid = os.getpid()
    try:
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring semaphore write lock.")
        lock.acquire_write_lock()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore write has been locked.")
        yield
    except Exception as error:
        if _raised_by_fasteners(error):
            raise ConanException(f"Failed to acquire interprocess write lock: {error}") from error
        else:
            raise
    finally:
        lock.release_write_lock()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore write has been released.")


@contextmanager
def interprocess_read_lock(conan_api: Any) -> None:
    """ Context manager to acquire an interprocess read lock.

        This method uses the fasteners library to create an interprocess read lock, and serves as a
        proxy for the library. The lock is acquired using the InterProcessReaderWriterLock class,
        which allows multiple processes to safely access shared resources. The lock is released
        automatically when the context manager exits.

    :param conan_api: ConanAPI instance
    :return: None
    """
    filelock_path = _filelock_path(conan_api)
    lock = fasteners.InterProcessReaderWriterLock(filelock_path)
    pid = os.getpid()
    try:
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Acquiring semaphore read lock.")
        lock.acquire_read_lock()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore read has been locked.")
        yield
    except Exception as error:
        if _raised_by_fasteners(error):
            raise ConanException(f"Failed to acquire interprocess read lock: {error}")
        else:
            raise
    finally:
        lock.release_read_lock()
        ConanOutput().debug(f"{datetime.now()} [{pid}]: Semaphore read has been released.")
