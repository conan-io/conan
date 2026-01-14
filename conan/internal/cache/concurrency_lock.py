import atexit
import errno
import hashlib
import os
import signal
import sys
import threading
from contextlib import contextmanager
from threading import RLock

import fasteners

from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.util.files import mkdir


class LockLevel:
    """
    Lock hierarchy levels to prevent ABBA deadlocks.

    Locks must be acquired in ascending level order. If a thread holds a lock
    at level N, it can only acquire locks at level N (reentrant) or higher.

    This prevents deadlock scenarios where:
    - Thread 1 holds lock A, wants lock B
    - Thread 2 holds lock B, wants lock A

    By enforcing ordering, all threads acquire locks in the same order.
    """
    CONFIG = 10
    RECIPE = 20
    SOURCE = 30
    PACKAGE = 40


class ConcurrencyLock:
    """
    Inter-process and thread-safe lock for Conan operations.

    Uses fasteners.InterProcessLock for cross-process synchronization and
    threading.RLock for thread safety within a single process.

    Lock Hierarchy:
        To prevent deadlocks when acquiring multiple locks, locks must be
        acquired in a specific order based on their level (lower levels first,
        higher levels later). Attempting to acquire a lower-level lock while
        holding a higher-level lock will raise a ConanException.

    Lock files are stored in {folder}/locks/

    Signal Handling:
        The class registers signal handlers for SIGTERM and SIGQUIT to ensure
        lock files are cleaned up when a process is terminated. An atexit
        handler is also registered for normal process exits.
    """
    _LOCKS_FOLDER = "locks"
    _HASH_LENGTH = 16

    # Class-level storage for thread locks, shared across all instances
    # Keyed by lock file path to ensure same lock is used for same resource
    # NOTE: it is expected that this accumulates locks
    _thread_locks = {}

    # Thread-local storage for tracking held locks per thread
    # Each thread has its own dict of {locks_path: [(lock_id, level), ...]}
    # Scoped by locks_path so different cache folders don't conflict
    _thread_local = threading.local()

    # Track active locks for cleanup on signals/exit
    # Dict of {lock_file_path: (process_lock, lock_id)}
    _active_locks = {}
    _active_locks_lock = threading.Lock()

    # Track whether signal handlers have been registered
    _handlers_registered = False
    _original_handlers = {}

    def __init__(self, folder):
        self._locks_path = os.path.join(folder, self._LOCKS_FOLDER)
        # Ensure signal handlers are registered on first use
        self._register_signal_handlers()

    @classmethod
    def _register_signal_handlers(cls):
        """
        Register signal handlers for cleanup on process termination.

        Registers handlers for SIGTERM and SIGQUIT (on Unix) that clean up
        lock files before the process exits. Also registers an atexit handler.

        This method is idempotent - it only registers handlers once.
        """
        if cls._handlers_registered:
            return

        # Register atexit handler for normal exits
        atexit.register(cls._cleanup_all_locks)

        # Register signal handlers (Unix only - Windows doesn't support these signals well)
        if sys.platform != "win32":
            for sig in (signal.SIGTERM, signal.SIGQUIT):
                try:
                    cls._original_handlers[sig] = signal.signal(sig, cls._signal_handler)
                except (OSError, ValueError):
                    # Signal may not be available or we're not in the main thread
                    pass

        cls._handlers_registered = True

    @classmethod
    def _signal_handler(cls, signum, frame):
        """
        Signal handler that cleans up locks and re-raises the signal.

        Args:
            signum: The signal number received
            frame: The current stack frame
        """
        # Clean up all active locks
        cls._cleanup_all_locks()

        # Restore original handler and re-raise signal for default behavior
        original = cls._original_handlers.get(signum, signal.SIG_DFL)
        signal.signal(signum, original)
        os.kill(os.getpid(), signum)

    @classmethod
    def _cleanup_all_locks(cls):
        """
        Clean up all active locks held by this process.

        Deletes lock files and releases process locks. Called by signal
        handlers and atexit.
        """
        with cls._active_locks_lock:
            for lock_file, (process_lock, lock_id) in list(cls._active_locks.items()):
                try:
                    os.unlink(lock_file)
                except OSError:
                    pass
                try:
                    process_lock.release()
                except Exception:
                    pass
            cls._active_locks.clear()

    def _lock_path(self, lock_id):
        """Get the filesystem path for a lock file"""
        mkdir(self._locks_path)
        return os.path.join(self._locks_path, lock_id)

    @staticmethod
    def _hash_ref(ref_repr):
        """Create a short hash from a reference string for use as lock ID"""
        h = hashlib.sha256(ref_repr.encode()).hexdigest()
        return h[:ConcurrencyLock._HASH_LENGTH]

    def _get_held_locks(self):
        """Get the stack of locks held by the current thread for this cache folder.

        Lock hierarchy is scoped per cache folder because locks on different
        cache folders protect different resources and cannot deadlock with each other.
        """
        if not hasattr(self._thread_local, 'held_locks'):
            self._thread_local.held_locks = {}
        if self._locks_path not in self._thread_local.held_locks:
            self._thread_local.held_locks[self._locks_path] = []
        return self._thread_local.held_locks[self._locks_path]

    def _check_lock_order(self, lock_id, level):
        """
        Check that acquiring this lock doesn't violate the lock hierarchy.

        Raises ConanException if a lock ordering violation is detected.
        """
        if level is None:
            return  # No ordering enforced for locks without a level

        held_locks = self._get_held_locks()
        for held_id, held_level in held_locks:
            if held_level is None:
                continue  # Locks without a level don't participate in ordering
            if held_id == lock_id:
                continue  # Reentrant acquisition of same lock is OK
            if level < held_level:
                # Build helpful error message with all currently held locks
                held_lock_info = ", ".join([f"'{hid}' (level {hlvl})"
                                            for hid, hlvl in held_locks if hlvl is not None])
                raise ConanException(
                    f"Lock ordering violation: cannot acquire lock '{lock_id}' (level {level}) "
                    f"while holding lock '{held_id}' (level {held_level}). "
                    f"Locks must be acquired in ascending level order to prevent deadlocks. "
                    f"Currently held locks: {held_lock_info}.\n"
                    f"Solution: Release higher-level locks (>= {held_level}) before acquiring "
                    f"lower-level locks (< {held_level}), or restructure code to acquire locks "
                    f"in ascending order."
                )

    @staticmethod
    def _is_lock_file_valid(process_lock):
        """
        Check if the lock file is still valid (hasn't been deleted by another process).

        Uses st_nlink to detect if the file has been unlinked. When a file is deleted
        on Unix, st_nlink becomes 0, but the file descriptor remains valid until closed.

        Returns:
            True if the lock file is valid, False if it was deleted.
        """
        try:
            # Get the file descriptor from fasteners' internal lockfile handle
            if process_lock.lockfile is None:
                return True  # Can't check, assume valid
            fd = process_lock.lockfile.fileno()
            st = os.fstat(fd)
            # st_nlink == 0 means file was deleted (unlinked) from filesystem
            return st.st_nlink > 0
        except (OSError, AttributeError, ValueError):
            # If we can't check, assume the lock is valid
            return True

    @contextmanager
    def lock(self, lock_id, wait_msg=None, level=None):
        """
        Acquire an exclusive lock on a resource.

        Args:
            lock_id: Unique identifier for the resource to lock
            wait_msg: Optional message to display if waiting for lock
            level: Lock hierarchy level for deadlock prevention (default: None)

        Raises:
            ConanException: If acquiring this lock would violate the lock hierarchy.

        Note:
            This implementation uses the st_nlink check pattern to safely clean up
            lock files after use. When releasing a lock, the file is deleted BEFORE
            releasing the lock. Processes that were waiting will detect the deletion
            (st_nlink == 0) and retry with a new lock file.
        """
        # Check lock ordering before attempting to acquire
        self._check_lock_order(lock_id, level)

        lock_file = self._lock_path(lock_id)

        # Acquire lock with retry loop for st_nlink check pattern
        # If another process deleted the lock file while we were waiting,
        # we need to retry with a new file
        wait_msg_shown = False
        while True:
            process_lock = fasteners.InterProcessLock(lock_file)

            # Try to acquire immediately (non-blocking)
            acquired = process_lock.acquire(blocking=False)

            if not acquired:
                # Lock is held by another process, show message and wait
                if not wait_msg_shown:
                    if wait_msg:
                        ConanOutput().info(wait_msg)
                    else:
                        ConanOutput().info(f"Waiting for lock...")
                    wait_msg_shown = True

                process_lock.acquire(blocking=True)  # Wait indefinitely, user can Ctrl+C

            # Check if the lock file is still valid (st_nlink > 0)
            # If another process deleted it while we were waiting, we acquired
            # a lock on a "ghost" inode and need to retry
            if self._is_lock_file_valid(process_lock):
                break  # Lock is valid, proceed

            # Lock file was deleted, release and retry with new file
            process_lock.release()

        # Track this lock for cleanup on signals/exit
        with self._active_locks_lock:
            self._active_locks[lock_file] = (process_lock, lock_id)

        try:
            # Also acquire thread lock for thread safety within this process
            # Use RLock to allow reentrant locking from the same thread, matching
            # the behavior of fasteners.InterProcessLock which is also reentrant
            thread_lock = self._thread_locks.setdefault(lock_file, RLock())
            thread_lock.acquire()

            # Track this lock as held by current thread
            held_locks = self._get_held_locks()
            held_locks.append((lock_id, level))

            try:
                yield
            finally:
                # Remove from held locks
                held_locks.pop()
                thread_lock.release()
        finally:
            # Remove from active locks tracking
            with self._active_locks_lock:
                self._active_locks.pop(lock_file, None)

            # Delete lock file BEFORE releasing the lock
            # This is the key to the st_nlink pattern: any process waiting on this
            # lock will acquire a lock on the now-deleted inode, detect st_nlink == 0,
            # and retry with a new file
            try:
                os.unlink(lock_file)
            except FileNotFoundError:
                # Expected - another process cleaned it up first (race condition by design)
                pass
            except OSError as e:
                # Unexpected errors - log for debugging but don't raise
                # (raising would break finally block cleanup and leave resources locked)
                if e.errno == errno.EACCES:
                    ConanOutput().warning(
                        f"Cannot delete lock file {lock_file}: Permission denied. "
                        f"Lock files may accumulate in {self._locks_path}",
                        warn_tag="locks"
                    )
                elif e.errno == errno.EISDIR:
                    ConanOutput().error(
                        f"Lock file is a directory: {lock_file}. "
                        f"This indicates filesystem corruption or a bug."
                    )
                elif e.errno == errno.EROFS:
                    ConanOutput().warning(
                        f"Cannot delete lock file {lock_file}: Read-only filesystem. "
                        f"Lock files may accumulate.",
                        warn_tag="locks"
                    )
                else:
                    # Other unexpected errors - log at debug level to avoid noise
                    ConanOutput().debug(f"Lock cleanup warning for {lock_file}: {e}")
            process_lock.release()

    @contextmanager
    def recipe_lock(self, ref, wait_msg=None):
        """
        Acquire a lock for recipe operations.

        Lock level: RECIPE

        Args:
            ref: RecipeReference to lock
            wait_msg: Optional message to display if waiting
        """
        lock_id = f"recipe_{self._hash_ref(ref.repr_notime())}"
        if wait_msg is None:
            wait_msg = f"Waiting for lock on recipe {ref.repr_notime()}..."
        with self.lock(lock_id, wait_msg=wait_msg, level=LockLevel.RECIPE):
            yield

    @contextmanager
    def package_lock(self, pref, wait_msg=None):
        """
        Acquire a lock for package operations.

        Lock level: PACKAGE

        Args:
            pref: PkgReference to lock
            wait_msg: Optional message to display if waiting
        """
        lock_id = f"package_{self._hash_ref(pref.repr_notime())}"
        if wait_msg is None:
            wait_msg = f"Waiting for lock on package {pref.repr_notime()}..."
        with self.lock(lock_id, wait_msg=wait_msg, level=LockLevel.PACKAGE):
            yield

    @contextmanager
    def config_lock(self, config_name, wait_msg=None):
        """
        Acquire a lock for configuration file operations.

        Lock level: CONFIG

        Args:
            config_name: Name of the config file (e.g., "remotes.json")
            wait_msg: Optional message to display if waiting
        """
        lock_id = f"config_{config_name}"
        if wait_msg is None:
            wait_msg = f"Waiting for lock on config {config_name}..."
        with self.lock(lock_id, wait_msg=wait_msg, level=LockLevel.CONFIG):
            yield

    @contextmanager
    def source_lock(self, ref, wait_msg=None):
        """
        Acquire a lock for source folder operations (source() method, exports_sources).

        Lock level: SOURCE

        Args:
            ref: RecipeReference to lock source operations for
            wait_msg: Optional message to display if waiting
        """
        lock_id = f"source_{self._hash_ref(ref.repr_notime())}"
        if wait_msg is None:
            wait_msg = f"Waiting for source lock on {ref.repr_notime()}..."
        with self.lock(lock_id, wait_msg=wait_msg, level=LockLevel.SOURCE):
            yield
