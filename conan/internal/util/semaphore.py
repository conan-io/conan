from typing import Callable, TypeVar, Any, Optional, Literal
import functools
import os
import tempfile
from datetime import datetime
from conan.errors import ConanException
from conan.api.output import ConanOutput

LockType = Literal["default", "read", "write"]
CONAN_SEMAPHORE_TIMEOUT = 300.0  # 5 minutes

def _lockfile_path() -> str:
    """Return the path to the lock file.

    Returns:
        str: Path to the lock file in the temporary directory
    """
    return os.path.join(tempfile.gettempdir(), "conan.lock")

def _create_lock_decorator(lock_type: LockType = "default", timeout: Optional[float] = None) -> Callable:
    """Factory function to create lock decorators.

    Args:
        lock_type: Type of lock - "default", "read", or "write"
        timeout: Maximum time to wait for lock acquisition in seconds.

    Returns:
        Callable: A decorator function that implements the specified locking behavior
    """
    timeout = timeout or CONAN_SEMAPHORE_TIMEOUT

    def decorator(func) -> Callable:
        @functools.wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            import fasteners
            pid = os.getpid()

            # Configure lock based on type
            if lock_type in ("read", "write"):
                lock = fasteners.InterProcessReaderWriterLock(_lockfile_path())
                acquire_method = (lock.acquire_read_lock if lock_type == "read"
                                else lock.acquire_write_lock)
                release_method = (lock.release_read_lock if lock_type == "read"
                                else lock.release_write_lock)
            else:
                lock = fasteners.InterProcessLock(_lockfile_path())
                acquire_method = lock.acquire
                release_method = lock.release

            # Log lock attempt
            ConanOutput().debug(f"{datetime.now()} [{pid}]: Getting {lock_type} lock.")

            # Acquire lock
            acquired = acquire_method(timeout=timeout)
            if not acquired:
                raise ConanException(
                    f"Conan could not acquire {lock_type} lock within "
                    f"{timeout} seconds during parallel process execution."
                )

            try:
                ConanOutput().debug(f"{datetime.now()} [{pid}]: {lock_type.capitalize()} locked.")
                return func(self, *args, **kwargs)
            finally:
                if acquired:
                    ConanOutput().debug(f"{datetime.now()} [{pid}]: {lock_type.capitalize()} released.")
                    release_method()

        return wrapper
    return decorator

def interprocess_lock(timeout: Optional[float] = None):
    """Decorator for inter-process locking."""
    return _create_lock_decorator("default", timeout)

def interprocess_write_lock(timeout: Optional[float] = None):
    """Decorator for inter-process write locking."""
    return _create_lock_decorator("write", timeout)

def interprocess_read_lock(timeout: Optional[float] = None):
    """Decorator for inter-process read locking."""
    return _create_lock_decorator("read", timeout)
