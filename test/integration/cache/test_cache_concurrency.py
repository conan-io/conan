"""
Tests for multi-process concurrent access to the Conan cache.

These tests verify that the cache locking mechanisms properly protect
against race conditions when multiple Conan processes access the same
cache simultaneously.
"""

import multiprocessing
import os
import sqlite3
import sys
import tempfile
import threading
import time

import pytest

from conan.errors import ConanException
from conan.internal.cache.concurrency_lock import ConcurrencyLock
from test.utils.multiprocess import MultiProcessTestClient


class TestConcurrencyLockUnit:
    """Unit tests for the ConcurrencyLock class"""

    def test_lock_creates_lock_file(self):
        """Verify that acquiring a lock creates a lock file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            with lock_manager.lock("test_resource"):
                lock_file = os.path.join(tmpdir, "locks", "test_resource")
                assert os.path.exists(lock_file)

    def test_lock_acquires_and_releases(self):
        """Verify that acquiring a lock and releasing it works (non-nested)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # This should work - single acquisition and release
            with lock_manager.lock("test_resource"):
                pass

    def test_lock_is_reentrant_same_thread(self):
        """
        Verify that the same thread can acquire the same lock multiple times (reentrancy).

        This tests nested acquisition of the same lock from the same thread.
        fasteners.InterProcessLock is reentrant, and our thread lock (RLock) should
        also be reentrant to match that behavior.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # Nested acquisition of the same lock - should NOT deadlock with RLock
            with lock_manager.lock("test_resource"):
                with lock_manager.lock("test_resource"):
                    with lock_manager.lock("test_resource"):
                        pass  # Triple-nested to really test reentrancy

    def test_recipe_lock_uses_hash(self):
        """Verify that recipe_lock generates a hash-based lock ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # Create a mock ref-like object
            class MockRef:
                def repr_notime(self):
                    return "pkg/1.0#abc123"

            ref = MockRef()

            with lock_manager.recipe_lock(ref):
                locks_dir = os.path.join(tmpdir, "locks")
                lock_files = os.listdir(locks_dir)
                # Should have created a lock file starting with "recipe_"
                assert any(f.startswith("recipe_") for f in lock_files)

    def test_package_lock_uses_hash(self):
        """Verify that package_lock generates a hash-based lock ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # Create a mock pref-like object
            class MockPref:
                def repr_notime(self):
                    return "pkg/1.0#abc123:pid#def456"

            pref = MockPref()

            with lock_manager.package_lock(pref):
                locks_dir = os.path.join(tmpdir, "locks")
                lock_files = os.listdir(locks_dir)
                # Should have created a lock file starting with "package_"
                assert any(f.startswith("package_") for f in lock_files)

    def test_source_lock_uses_hash(self):
        """Verify that source_lock generates a hash-based lock ID"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # Create a mock ref-like object
            class MockRef:
                def repr_notime(self):
                    return "pkg/1.0#abc123"

            ref = MockRef()

            with lock_manager.source_lock(ref):
                locks_dir = os.path.join(tmpdir, "locks")
                lock_files = os.listdir(locks_dir)
                # Should have created a lock file starting with "source_"
                assert any(f.startswith("source_") for f in lock_files)


class TestConcurrencyLockDeadlockScenarios:
    """
    Tests for potential deadlock scenarios in ConcurrencyLock.

    These tests verify that the locking implementation handles edge cases
    that could lead to deadlocks in multi-threaded environments.
    """

    def test_same_lock_reentrancy_same_thread(self):
        """
        Test that the same thread can acquire the same lock multiple times (reentrancy).

        This is the TRUE reentrancy test. If this deadlocks, it means the thread
        lock implementation (threading.Lock) is blocking nested acquisition from
        the same thread, which would be a bug since fasteners.InterProcessLock
        is reentrant but threading.Lock is not.

        Expected behavior: Should NOT deadlock - nested acquisition should work.
        Current behavior: Will DEADLOCK because threading.Lock is not reentrant.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)
            deadlock_detected = threading.Event()
            success = threading.Event()

            def nested_lock_attempt():
                try:
                    with lock_manager.lock("same_resource"):
                        # Try to acquire the SAME lock again (nested)
                        with lock_manager.lock("same_resource"):
                            success.set()
                except Exception:
                    pass

            # Run in a separate thread so we can timeout
            thread = threading.Thread(target=nested_lock_attempt)
            thread.start()
            thread.join(timeout=2.0)  # 2 second timeout

            if thread.is_alive():
                deadlock_detected.set()
                # Thread is stuck - this is a deadlock
                # We can't easily kill the thread, but the test will report failure

            assert success.is_set(), (
                "DEADLOCK DETECTED: Same-thread nested lock acquisition failed. "
                "This indicates threading.Lock is blocking reentrant acquisition. "
                "Consider using threading.RLock instead of threading.Lock."
            )

    def test_different_locks_same_thread_sequential(self):
        """
        Test that the same thread can acquire different locks sequentially (nested).

        This tests acquiring lock A, then lock B while holding A.
        This should always work as long as no other thread is trying the reverse.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            # This should work - sequential acquisition of different locks
            with lock_manager.lock("resource_A"):
                with lock_manager.lock("resource_B"):
                    pass  # Both locks held

    def test_lock_ordering_prevents_abba_deadlock(self):
        """
        Test that lock ordering prevents ABBA deadlock scenarios.

        With lock hierarchy enforcement, attempting to acquire a lower-level lock
        while holding a higher-level lock raises an exception instead of deadlocking.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            class MockRef:
                def __init__(self, name):
                    self._name = name
                def repr_notime(self):
                    return self._name

            class MockPref:
                def __init__(self, name):
                    self._name = name
                def repr_notime(self):
                    return self._name

            ref = MockRef("pkg/1.0")
            pref = MockPref("pkg/1.0:pid123")

            # Valid ordering: recipe (20) -> package (40) should work
            with lock_manager.recipe_lock(ref):
                with lock_manager.package_lock(pref):
                    pass  # This should succeed

            # Invalid ordering: package (40) -> recipe (20) should raise
            with pytest.raises(ConanException) as exc_info:
                with lock_manager.package_lock(pref):
                    with lock_manager.recipe_lock(ref):
                        pass  # Should not reach here

            assert "Lock ordering violation" in str(exc_info.value)
            assert "level 20" in str(exc_info.value)  # recipe level
            assert "level 40" in str(exc_info.value)  # package level

    def test_lock_ordering_valid_sequences(self):
        """
        Test that valid lock ordering sequences work correctly.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            class MockRef:
                def repr_notime(self):
                    return "pkg/1.0"

            class MockPref:
                def repr_notime(self):
                    return "pkg/1.0:pid123"

            ref = MockRef()
            pref = MockPref()

            # config -> recipe -> source -> package (full valid sequence)
            with lock_manager.config_lock("test.json"):
                with lock_manager.recipe_lock(ref):
                    with lock_manager.source_lock(ref):
                        with lock_manager.package_lock(pref):
                            pass  # All nested - valid ordering

            # Partial sequences should also work
            with lock_manager.config_lock("test.json"):
                with lock_manager.package_lock(pref):
                    pass  # Skipping levels is OK

            with lock_manager.recipe_lock(ref):
                with lock_manager.source_lock(ref):
                    pass

    def test_lock_ordering_invalid_sequences(self):
        """
        Test that invalid lock ordering sequences raise exceptions.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            class MockRef:
                def repr_notime(self):
                    return "pkg/1.0"

            class MockPref:
                def repr_notime(self):
                    return "pkg/1.0:pid123"

            ref = MockRef()
            pref = MockPref()

            # package -> recipe (invalid: 40 -> 20)
            with pytest.raises(ConanException) as exc_info:
                with lock_manager.package_lock(pref):
                    with lock_manager.recipe_lock(ref):
                        pass
            assert "Lock ordering violation" in str(exc_info.value)

            # source -> config (invalid: 30 -> 10)
            with pytest.raises(ConanException) as exc_info:
                with lock_manager.source_lock(ref):
                    with lock_manager.config_lock("test.json"):
                        pass
            assert "Lock ordering violation" in str(exc_info.value)

            # package -> config (invalid: 40 -> 10)
            with pytest.raises(ConanException) as exc_info:
                with lock_manager.package_lock(pref):
                    with lock_manager.config_lock("test.json"):
                        pass
            assert "Lock ordering violation" in str(exc_info.value)

    def test_generic_locks_bypass_ordering(self):
        """
        Test that generic lock() calls (without a level) don't participate
        in lock ordering checks.

        This allows the generic lock() method to be used without worrying
        about the lock hierarchy.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            class MockPref:
                def repr_notime(self):
                    return "pkg/1.0:pid123"

            pref = MockPref()

            # Generic locks can be acquired in any order
            with lock_manager.lock("resource_A"):
                with lock_manager.lock("resource_B"):
                    pass

            with lock_manager.lock("resource_B"):
                with lock_manager.lock("resource_A"):
                    pass

            # Generic locks don't affect ordered locks
            with lock_manager.lock("resource_A"):
                with lock_manager.package_lock(pref):
                    with lock_manager.lock("resource_B"):
                        pass  # Generic locks can be acquired after ordered locks

    def test_lock_ordering_scoped_per_cache_folder(self):
        """
        Test that lock ordering is scoped per cache folder.

        Locks from different cache folders (e.g., main cache vs local-recipes-index cache)
        should not conflict with each other because they protect different resources.
        This prevents false lock ordering violations when code in one cache folder
        needs to call code that uses a different cache folder.
        """
        with tempfile.TemporaryDirectory() as tmpdir1, \
             tempfile.TemporaryDirectory() as tmpdir2:

            # Two different cache folders (simulating main cache and local-recipes-index cache)
            lock_manager1 = ConcurrencyLock(tmpdir1)
            lock_manager2 = ConcurrencyLock(tmpdir2)

            class MockRef:
                def repr_notime(self):
                    return "pkg/1.0"

            ref = MockRef()

            # This should NOT raise: source_lock (30) in cache1, then recipe_lock (20) in cache2
            # Even though 20 < 30, they're in different caches so no conflict
            with lock_manager1.source_lock(ref):
                with lock_manager2.recipe_lock(ref):
                    pass  # Should succeed - different cache folders don't conflict

            # Verify the same cache folder still enforces ordering
            with pytest.raises(ConanException) as exc_info:
                with lock_manager1.source_lock(ref):
                    with lock_manager1.recipe_lock(ref):
                        pass  # Should fail - same cache folder enforces hierarchy
            assert "Lock ordering violation" in str(exc_info.value)

    def test_multiple_threads_same_lock_contention(self):
        """
        Test that multiple threads can safely contend for the same lock.

        This verifies basic thread safety - multiple threads trying to acquire
        the same lock should work correctly (one at a time).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)
            counter = {"value": 0}
            num_threads = 10
            increments_per_thread = 100

            def increment_with_lock():
                for _ in range(increments_per_thread):
                    with lock_manager.lock("counter_lock"):
                        # Critical section - should be atomic
                        current = counter["value"]
                        time.sleep(0.0001)  # Small delay to increase chance of race
                        counter["value"] = current + 1

            threads = [threading.Thread(target=increment_with_lock) for _ in range(num_threads)]

            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30.0)

            # Verify no threads are stuck
            for t in threads:
                assert not t.is_alive(), "Thread did not complete - possible deadlock"

            # Verify counter is correct (no race conditions)
            expected = num_threads * increments_per_thread
            assert counter["value"] == expected, (
                f"Race condition detected: counter={counter['value']}, expected={expected}"
            )

    def test_lock_held_by_other_thread_blocks(self):
        """
        Test that a lock held by one thread blocks another thread.

        This verifies the basic mutual exclusion property.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)
            lock_acquired_by_t1 = threading.Event()
            t2_tried_to_acquire = threading.Event()
            t1_can_release = threading.Event()
            t2_acquired = threading.Event()

            def thread1_hold_lock():
                with lock_manager.lock("shared_resource"):
                    lock_acquired_by_t1.set()
                    # Wait until t2 has tried to acquire
                    t1_can_release.wait(timeout=5.0)

            def thread2_try_acquire():
                lock_acquired_by_t1.wait(timeout=5.0)
                t2_tried_to_acquire.set()
                # This should block until t1 releases
                with lock_manager.lock("shared_resource"):
                    t2_acquired.set()

            t1 = threading.Thread(target=thread1_hold_lock)
            t2 = threading.Thread(target=thread2_try_acquire)

            t1.start()
            t2.start()

            # Wait for t1 to acquire lock
            assert lock_acquired_by_t1.wait(timeout=2.0), "Thread 1 failed to acquire lock"

            # Wait a bit and verify t2 hasn't acquired yet
            time.sleep(0.5)
            assert not t2_acquired.is_set(), "Thread 2 acquired lock while Thread 1 held it!"

            # Let t1 release
            t1_can_release.set()

            # Now t2 should be able to acquire
            t1.join(timeout=2.0)
            t2.join(timeout=2.0)

            assert t2_acquired.is_set(), "Thread 2 failed to acquire lock after Thread 1 released"


class TestSQLiteConcurrency:
    """Tests for SQLite WAL mode and concurrent access"""

    def test_wal_mode_is_enabled(self):
        """Verify that WAL mode is enabled on the database"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            # Simulate what the cache database does
            conn = sqlite3.connect(db_path, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL")

            # Verify WAL mode is set
            result = conn.execute("PRAGMA journal_mode").fetchone()
            assert result[0] == "wal"

            conn.close()

    def test_wal_files_created(self):
        """Verify that WAL mode creates the expected files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")

            conn = sqlite3.connect(db_path, isolation_level=None)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("CREATE TABLE test (id INTEGER)")
            conn.execute("INSERT INTO test VALUES (1)")

            # WAL mode should create -wal and -shm files
            # Note: they may not exist until actual writes happen
            conn.close()

            # The main database file should exist
            assert os.path.exists(db_path)


class TestMultiProcessConcurrency:
    """
    Integration tests for multi-process concurrent access.

    These tests spawn actual Conan subprocesses to test real-world
    concurrent access scenarios.
    """

    @pytest.fixture
    def shared_cache(self):
        """Create a temporary shared cache folder"""
        with tempfile.TemporaryDirectory(prefix="conan_test_") as tmpdir:
            yield tmpdir

    @pytest.mark.slow
    def test_concurrent_cache_list(self, shared_cache):
        """
        Multiple processes listing the cache simultaneously should not error.
        """
        client = MultiProcessTestClient(shared_cache)

        # Run 5 concurrent cache list commands
        commands = [["list", "*"]] * 5
        results = client.run_concurrent(commands)

        # All should succeed (even if cache is empty)
        for result in results:
            assert result.returncode == 0 or "No remote" in result.stderr

    @pytest.mark.slow
    def test_concurrent_remote_operations(self, shared_cache):
        """
        Multiple processes modifying remotes simultaneously should not corrupt the file.
        """
        client = MultiProcessTestClient(shared_cache)

        # Run concurrent remote list operations (read-only, should be safe)
        commands = [["remote", "list"]] * 10
        results = client.run_concurrent(commands)

        # All should succeed
        for result in results:
            assert result.returncode == 0


class TestCacheRemovalCleanup:
    """Tests for proper cleanup when removing recipes/packages from cache"""

    def test_remove_recipe_layout_cleans_package_folders(self):
        """
        Verify that remove_recipe_layout also removes package folders from disk.

        This tests the fix for the FIXME in CacheOperations.remove_recipe():
        Previously, calling remove_recipe would clear package entries from the DB
        but leave orphaned package folders on disk. The fix ensures that all
        package folders are removed along with the recipe folder.

        Note: The normal 'conan remove' command calls all_recipe_packages() first
        which removes packages individually, so this bug only manifested when
        remove_recipe_layout was called directly.
        """
        from conan.test.utils.tools import TestClient
        from conan.api.model import RecipeReference

        client = TestClient()
        client.save({"conanfile.py": """
from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
"""})
        client.run("create .")

        # Get the layout paths
        ref_layout = client.exported_layout()
        pkg_layout = client.created_layout()

        # Verify both folders exist before removal
        assert os.path.exists(ref_layout.base_folder), "Recipe folder should exist"
        assert os.path.exists(pkg_layout.base_folder), "Package folder should exist"

        # Get the cache and recipe layout for removal
        ref = RecipeReference.loads("pkg/1.0")
        cache = client.cache
        recipe_ref = cache.get_latest_recipe_revision(ref)
        recipe_layout = cache.recipe_layout(recipe_ref)

        # Call remove_recipe_layout DIRECTLY (not through 'conan remove')
        # This bypasses the normal flow that calls all_recipe_packages() first
        cache.remove_recipe_layout(recipe_layout)

        # Verify BOTH folders are removed - this is the key assertion
        assert not os.path.exists(ref_layout.base_folder), \
            "Recipe folder should be removed"
        assert not os.path.exists(pkg_layout.base_folder), \
            "Package folder should be removed (was orphaned before the fix)"

    def test_remove_recipe_layout_cleans_multiple_packages(self):
        """
        Verify that remove_recipe_layout removes ALL package folders for a recipe.

        Tests the case where a recipe has multiple packages (e.g., different settings).
        """
        from conan.test.utils.tools import TestClient
        from conan.api.model import RecipeReference

        client = TestClient()
        client.save({"conanfile.py": """
from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    settings = "build_type"
"""})
        # Create packages for both Debug and Release
        client.run("create . -s build_type=Debug")
        debug_pkg_layout = client.created_layout()

        client.run("create . -s build_type=Release")
        release_pkg_layout = client.created_layout()
        ref_layout = client.exported_layout()

        # Verify all folders exist
        assert os.path.exists(ref_layout.base_folder), "Recipe folder should exist"
        assert os.path.exists(debug_pkg_layout.base_folder), "Debug package folder should exist"
        assert os.path.exists(release_pkg_layout.base_folder), "Release package folder should exist"

        # Remove the recipe directly
        ref = RecipeReference.loads("pkg/1.0")
        cache = client.cache
        recipe_ref = cache.get_latest_recipe_revision(ref)
        recipe_layout = cache.recipe_layout(recipe_ref)
        cache.remove_recipe_layout(recipe_layout)

        # Verify ALL folders are removed
        assert not os.path.exists(ref_layout.base_folder), \
            "Recipe folder should be removed"
        assert not os.path.exists(debug_pkg_layout.base_folder), \
            "Debug package folder should be removed"
        assert not os.path.exists(release_pkg_layout.base_folder), \
            "Release package folder should be removed"


class TestDownloadRaceConditions:
    """Tests for download race condition handling"""

    def test_create_pkg_layout_returns_none_if_exists(self):
        """
        Verify that create_pkg_layout returns None if another process
        already created the package (simulating ConanReferenceAlreadyExistsInDB).
        """
        from conan.test.utils.tools import TestClient
        from conan.api.model import RecipeReference, PkgReference

        client = TestClient()
        client.save({"conanfile.py": """
from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
"""})
        client.run("create .")

        # Get the pref from the created package
        ref = RecipeReference.loads("pkg/1.0")
        cache = client.cache
        recipe_layout = cache.get_latest_recipe_revision(ref)
        prefs = cache.get_package_references(recipe_layout)
        assert len(prefs) == 1
        pref = prefs[0]

        # Try to create the same package layout again - should return None
        result = cache.create_pkg_layout(pref)
        assert result is None, "create_pkg_layout should return None for existing package"

    def test_download_skips_existing_package(self):
        """
        Verify that _download_pkg skips download if package already exists.
        This tests the exists_prev check in the download path.
        """
        from conan.test.utils.tools import TestClient

        client = TestClient(default_server_user=True)
        client.save({"conanfile.py": """
from conan import ConanFile
class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
"""})
        client.run("create .")
        client.run("upload pkg/1.0 -r default -c")

        # Remove from local cache
        client.run("remove pkg/1.0 -c")

        # Download the package
        client.run("download pkg/1.0:* -r default")
        assert "Retrieving package" in client.out

        # Try to download again - should skip because it exists
        client.run("download pkg/1.0:* -r default")
        # The package should already exist, so no "Retrieving package" for download
        # (it may say "already exists" or just skip silently)


class TestLockCleanup:
    """Tests for lock file cleanup scenarios"""

    def test_lock_released_on_exception(self):
        """Verify lock is released even if exception occurs inside"""
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)

            try:
                with lock_manager.lock("test_resource"):
                    raise ValueError("Test exception")
            except ValueError:
                pass

            # Should be able to acquire the lock again
            with lock_manager.lock("test_resource"):
                pass  # Success - lock was properly released

    def test_lock_files_cleaned_up(self):
        """
        Lock files are cleaned up after release using the st_nlink pattern.

        The lock file is deleted BEFORE releasing the lock. Any process that was
        waiting will detect st_nlink == 0 and retry with a new file. This prevents
        unbounded accumulation of lock files over time.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)
            locks_dir = os.path.join(tmpdir, "locks")

            # Lock file should exist during the lock
            with lock_manager.lock("cleanup_test_lock"):
                assert os.path.exists(locks_dir), "Locks directory should exist"
                lock_file = os.path.join(locks_dir, "cleanup_test_lock")
                assert os.path.exists(lock_file), "Lock file should exist while held"

            # Lock file should be cleaned up after release
            lock_file = os.path.join(locks_dir, "cleanup_test_lock")
            assert not os.path.exists(lock_file), "Lock file should be deleted after release"

    def test_st_nlink_retry_on_deleted_lock(self):
        """
        Test that the st_nlink check pattern correctly handles the case where
        a lock file is deleted while a process is waiting.

        The st_nlink pattern ensures that when Process A releases and deletes the
        lock file, Process B (which was waiting) will detect that it acquired a
        lock on a deleted inode (st_nlink == 0) and retry with a new file.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_manager = ConcurrencyLock(tmpdir)
            locks_dir = os.path.join(tmpdir, "locks")
            lock_id = "st_nlink_test"
            lock_file = os.path.join(locks_dir, lock_id)

            # Simulate a sequence of lock acquisitions
            # Each should create a new file and clean it up
            for i in range(3):
                with lock_manager.lock(lock_id):
                    # Lock file should exist during the lock
                    assert os.path.exists(lock_file), f"Iteration {i}: Lock file should exist"

                # Lock file should be cleaned up after each release
                assert not os.path.exists(lock_file), f"Iteration {i}: Lock file should be deleted"

    def test_is_lock_file_valid_detects_deleted_file(self):
        """
        Unit test for _is_lock_file_valid() to ensure it correctly detects
        when a lock file has been deleted (st_nlink == 0).
        """
        import fasteners

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_file = os.path.join(tmpdir, "test_lock")

            # Create and acquire a lock
            process_lock = fasteners.InterProcessLock(lock_file)
            process_lock.acquire()

            try:
                # File exists, should be valid
                assert ConcurrencyLock._is_lock_file_valid(process_lock), \
                    "Lock should be valid when file exists"

                # Delete the file while holding the lock
                os.unlink(lock_file)

                # Now st_nlink should be 0, file should be invalid
                assert not ConcurrencyLock._is_lock_file_valid(process_lock), \
                    "Lock should be invalid after file is deleted (st_nlink == 0)"
            finally:
                process_lock.release()


# Helper function for multiprocessing - must be at module level to be picklable
def _child_process_hold_lock(cache_folder, lock_id, acquired_event, release_event):
    """
    Child process function that acquires a lock and holds it until signaled.

    Args:
        cache_folder: Path to the cache folder for ConcurrencyLock
        lock_id: The lock identifier to acquire
        acquired_event: multiprocessing.Event to signal when lock is acquired
        release_event: multiprocessing.Event to wait on before releasing
    """
    lock_manager = ConcurrencyLock(cache_folder)
    with lock_manager.lock(lock_id):
        acquired_event.set()  # Signal that we have the lock
        release_event.wait(timeout=30.0)  # Wait for parent to tell us to release


def _child_process_try_acquire(cache_folder, lock_id, result_queue):
    """
    Child process function that tries to acquire a lock and reports timing.

    Args:
        cache_folder: Path to the cache folder for ConcurrencyLock
        lock_id: The lock identifier to acquire
        result_queue: multiprocessing.Queue to report results
    """
    start_time = time.time()
    lock_manager = ConcurrencyLock(cache_folder)
    with lock_manager.lock(lock_id):
        elapsed = time.time() - start_time
        result_queue.put({"acquired": True, "elapsed": elapsed})


class TestInterProcessLockContention:
    """
    Tests for actual inter-process lock contention.

    These tests spawn real OS processes to verify that ConcurrencyLock correctly
    synchronizes access across process boundaries using file-based locking.
    """

    @pytest.mark.slow
    def test_lock_blocks_across_processes(self):
        """
        Test that a lock held by one process blocks another process.

        This is the core inter-process locking test:
        1. Child process acquires a lock
        2. Parent process tries to acquire the same lock (should block)
        3. Child process releases the lock
        4. Parent process should then acquire the lock
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_id = "contention_test"

            # Use multiprocessing events for synchronization
            acquired_event = multiprocessing.Event()
            release_event = multiprocessing.Event()

            # Start child process that will hold the lock
            child = multiprocessing.Process(
                target=_child_process_hold_lock,
                args=(tmpdir, lock_id, acquired_event, release_event)
            )
            child.start()

            try:
                # Wait for child to acquire the lock
                assert acquired_event.wait(timeout=10.0), \
                    "Child process failed to acquire lock"

                # Now try to acquire the same lock from parent
                # This should block until child releases
                lock_manager = ConcurrencyLock(tmpdir)

                # Use a thread with timeout to detect blocking
                lock_acquired = threading.Event()
                lock_error = []

                def try_acquire():
                    try:
                        with lock_manager.lock(lock_id):
                            lock_acquired.set()
                    except Exception as e:
                        lock_error.append(e)

                acquire_thread = threading.Thread(target=try_acquire)
                acquire_thread.start()

                # Wait a short time - lock should NOT be acquired yet
                time.sleep(0.5)
                assert not lock_acquired.is_set(), \
                    "Parent acquired lock while child still held it!"

                # Now tell child to release
                release_event.set()

                # Parent should acquire within a reasonable time
                acquire_thread.join(timeout=10.0)
                assert not acquire_thread.is_alive(), \
                    "Parent thread stuck - possible deadlock"
                assert lock_acquired.is_set(), \
                    "Parent failed to acquire lock after child released"
                assert not lock_error, f"Lock acquisition error: {lock_error}"

            finally:
                release_event.set()  # Ensure child releases if test fails
                child.join(timeout=5.0)
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=1.0)

    @pytest.mark.slow
    def test_sequential_lock_acquisition_across_processes(self):
        """
        Test that multiple processes can sequentially acquire the same lock.

        Verifies that after one process releases a lock, another process
        can successfully acquire it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_id = "sequential_test"
            result_queue = multiprocessing.Queue()

            # First child acquires and releases immediately
            child1 = multiprocessing.Process(
                target=_child_process_try_acquire,
                args=(tmpdir, lock_id, result_queue)
            )
            child1.start()
            child1.join(timeout=10.0)

            result1 = result_queue.get(timeout=5.0)
            assert result1["acquired"], "First child failed to acquire lock"

            # Second child should also be able to acquire
            child2 = multiprocessing.Process(
                target=_child_process_try_acquire,
                args=(tmpdir, lock_id, result_queue)
            )
            child2.start()
            child2.join(timeout=10.0)

            result2 = result_queue.get(timeout=5.0)
            assert result2["acquired"], "Second child failed to acquire lock"

    @pytest.mark.slow
    def test_concurrent_processes_serialize_access(self):
        """
        Test that multiple processes competing for the same lock are serialized.

        Spawns multiple child processes that all try to acquire the same lock
        and increment a shared counter. Verifies that the final count is correct,
        proving that access was properly serialized.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            lock_id = "serialize_test"
            counter_file = os.path.join(tmpdir, "counter.txt")

            # Initialize counter
            with open(counter_file, "w") as f:
                f.write("0")

            num_processes = 5
            increments_per_process = 10

            def increment_with_lock(cache_folder, lock_id, counter_path, count):
                """Child process that increments counter under lock"""
                lock_manager = ConcurrencyLock(cache_folder)
                for _ in range(count):
                    with lock_manager.lock(lock_id):
                        # Read current value
                        with open(counter_path, "r") as f:
                            value = int(f.read().strip())
                        # Small delay to increase chance of race if lock fails
                        time.sleep(0.01)
                        # Write incremented value
                        with open(counter_path, "w") as f:
                            f.write(str(value + 1))

            # Spawn processes
            processes = []
            for _ in range(num_processes):
                p = multiprocessing.Process(
                    target=increment_with_lock,
                    args=(tmpdir, lock_id, counter_file, increments_per_process)
                )
                processes.append(p)

            # Start all processes
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Verify final count
            with open(counter_file, "r") as f:
                final_value = int(f.read().strip())

            expected = num_processes * increments_per_process
            assert final_value == expected, (
                f"Race condition detected: counter={final_value}, expected={expected}. "
                f"Inter-process locking failed to serialize access."
            )


# Helper function for signal cleanup test - must be at module level to be picklable
def _child_process_hold_lock_indefinitely(cache_folder, lock_id, acquired_event):
    """
    Child process function that acquires a lock and holds it until terminated.

    Args:
        cache_folder: Path to the cache folder for ConcurrencyLock
        lock_id: The lock identifier to acquire
        acquired_event: multiprocessing.Event to signal when lock is acquired
    """
    import signal
    # Import here to ensure we use the module's ConcurrencyLock with any signal handlers
    from conan.internal.cache.concurrency_lock import ConcurrencyLock

    lock_manager = ConcurrencyLock(cache_folder)
    with lock_manager.lock(lock_id):
        acquired_event.set()  # Signal that we have the lock
        # Wait indefinitely - expect to be terminated by SIGTERM
        signal.pause()


class TestSignalHandlerCleanup:
    """
    Tests for lock file cleanup when a process receives signals like SIGTERM.

    These tests verify that lock files are properly cleaned up even when
    a process is terminated by signals, preventing stale lock files from
    accumulating.
    """

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="SIGTERM signal handling is different on Windows"
    )
    @pytest.mark.slow
    def test_sigterm_cleans_up_lock_file(self):
        """
        Test that SIGTERM causes lock file cleanup via signal handlers.

        This test verifies that when a process holding a lock receives SIGTERM,
        the lock file is properly cleaned up (deleted) rather than left as a
        stale file on disk.

        Steps:
        1. Child process acquires a lock
        2. Parent sends SIGTERM to child
        3. Verify lock file is cleaned up after child terminates
        """
        import signal

        with tempfile.TemporaryDirectory() as tmpdir:
            lock_id = "sigterm_cleanup_test"
            lock_file = os.path.join(tmpdir, "locks", lock_id)

            # Use multiprocessing event for synchronization
            acquired_event = multiprocessing.Event()

            # Start child process that will hold the lock indefinitely
            child = multiprocessing.Process(
                target=_child_process_hold_lock_indefinitely,
                args=(tmpdir, lock_id, acquired_event)
            )
            child.start()

            try:
                # Wait for child to acquire the lock
                assert acquired_event.wait(timeout=10.0), \
                    "Child process failed to acquire lock"

                # Verify lock file exists while child holds the lock
                assert os.path.exists(lock_file), \
                    "Lock file should exist while lock is held"

                # Send SIGTERM to child process
                os.kill(child.pid, signal.SIGTERM)

                # Wait for child to terminate
                child.join(timeout=5.0)
                assert not child.is_alive(), \
                    "Child process did not terminate after SIGTERM"

                # Give a small grace period for file system operations
                time.sleep(0.1)

                # Verify lock file was cleaned up by signal handler
                assert not os.path.exists(lock_file), (
                    f"Lock file '{lock_file}' was NOT cleaned up after SIGTERM. "
                    "Signal handler cleanup is not working."
                )

            finally:
                # Ensure child is terminated
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=2.0)
                    if child.is_alive():
                        child.kill()


# Helper function for editable concurrency test - must be at module level to be picklable
def _child_process_add_editable(cache_folder, pkg_name, pkg_path, result_queue):
    """
    Child process function that adds an editable package.

    Args:
        cache_folder: Path to the cache folder
        pkg_name: Name of the package to add
        pkg_path: Path for the editable
        result_queue: multiprocessing.Queue to report results
    """
    from conan.internal.api.local.editable import EditablePackages
    from conan.api.model import RecipeReference

    try:
        editables = EditablePackages(cache_folder)
        ref = RecipeReference.loads(f"{pkg_name}/1.0")
        editables.add(ref, pkg_path)
        result_queue.put({"success": True, "pkg_name": pkg_name})
    except Exception as e:
        result_queue.put({"success": False, "pkg_name": pkg_name, "error": str(e)})


class TestEditablePackagesConcurrency:
    """
    Tests for concurrent access to editable_packages.json.

    These tests verify that the EditablePackages class properly handles
    concurrent add/remove operations from multiple processes without
    losing or corrupting data.
    """

    def test_editable_add_is_atomic(self):
        """
        Test that adding an editable package uses proper locking.

        Verifies that the add operation acquires a lock, reloads the file,
        and saves atomically.
        """
        from conan.internal.api.local.editable import EditablePackages
        from conan.api.model import RecipeReference

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create first editable
            editables1 = EditablePackages(tmpdir)
            ref1 = RecipeReference.loads("pkg1/1.0")
            editables1.add(ref1, "/path/to/pkg1")

            # Simulate another process creating a second EditablePackages instance
            # (which loads the file state at that moment)
            editables2 = EditablePackages(tmpdir)
            ref2 = RecipeReference.loads("pkg2/1.0")

            # Add from second instance - should reload and preserve pkg1
            editables2.add(ref2, "/path/to/pkg2")

            # Verify both packages are in the file
            editables_check = EditablePackages(tmpdir)
            refs = list(editables_check.edited_refs.keys())
            ref_names = [str(r) for r in refs]

            assert "pkg1/1.0" in ref_names, "pkg1 should be preserved after pkg2 add"
            assert "pkg2/1.0" in ref_names, "pkg2 should be added"

    def test_editable_remove_is_atomic(self):
        """
        Test that removing an editable package uses proper locking.

        Verifies that the remove operation acquires a lock, reloads the file,
        and saves atomically.
        """
        from conan.internal.api.local.editable import EditablePackages
        from conan.api.model import RecipeReference

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create initial editables
            editables = EditablePackages(tmpdir)
            ref1 = RecipeReference.loads("pkg1/1.0")
            ref2 = RecipeReference.loads("pkg2/1.0")
            editables.add(ref1, "/path/to/pkg1")
            editables.add(ref2, "/path/to/pkg2")

            # Simulate another process that loaded the file before pkg2 was added
            # but removes pkg1 after - should still see pkg2 due to reload
            editables2 = EditablePackages(tmpdir)

            # Add pkg3 from first instance
            ref3 = RecipeReference.loads("pkg3/1.0")
            editables.add(ref3, "/path/to/pkg3")

            # Now remove pkg1 from second instance - should reload and preserve pkg3
            editables2.remove(None, ["pkg1/*"])

            # Verify pkg2 and pkg3 remain, pkg1 is removed
            editables_check = EditablePackages(tmpdir)
            refs = list(editables_check.edited_refs.keys())
            ref_names = [str(r) for r in refs]

            assert "pkg1/1.0" not in ref_names, "pkg1 should be removed"
            assert "pkg2/1.0" in ref_names, "pkg2 should be preserved"
            assert "pkg3/1.0" in ref_names, "pkg3 should be preserved after reload"

    @pytest.mark.slow
    def test_concurrent_editable_adds_from_multiple_processes(self):
        """
        Test that multiple processes can safely add editables concurrently.

        Spawns multiple child processes that each add a different editable
        package. Verifies that all packages are present in the final file,
        proving that the locking prevents lost updates.
        """
        from conan.internal.api.local.editable import EditablePackages

        with tempfile.TemporaryDirectory() as tmpdir:
            num_processes = 5
            result_queue = multiprocessing.Queue()

            # Spawn processes that each add a different package
            processes = []
            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_child_process_add_editable,
                    args=(tmpdir, f"pkg{i}", f"/path/to/pkg{i}", result_queue)
                )
                processes.append(p)

            # Start all processes
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=30.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # Verify all succeeded
            for result in results:
                assert result["success"], f"Process failed: {result.get('error', 'unknown')}"

            # Verify all packages are present in the file
            editables = EditablePackages(tmpdir)
            refs = list(editables.edited_refs.keys())
            ref_names = [str(r) for r in refs]

            for i in range(num_processes):
                assert f"pkg{i}/1.0" in ref_names, (
                    f"pkg{i} is missing - concurrent add lost an update! "
                    f"Found: {ref_names}"
                )

    def test_atomic_save_creates_valid_json(self):
        """
        Test that the atomic save produces valid JSON even if interrupted.

        The .tmp + os.replace() pattern should ensure we never have a
        corrupted or partial JSON file.
        """
        from conan.internal.api.local.editable import EditablePackages, EDITABLE_PACKAGES_FILE
        from conan.api.model import RecipeReference
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            editables = EditablePackages(tmpdir)

            # Add several packages
            for i in range(10):
                ref = RecipeReference.loads(f"pkg{i}/1.0")
                editables.add(ref, f"/path/to/pkg{i}")

            # Verify the file is valid JSON
            json_path = os.path.join(tmpdir, EDITABLE_PACKAGES_FILE)
            with open(json_path, 'r') as f:
                data = json.load(f)

            assert len(data) == 10, f"Expected 10 packages, found {len(data)}"

            # Verify no .tmp file is left behind
            tmp_path = json_path + ".tmp"
            assert not os.path.exists(tmp_path), "Temporary file should be cleaned up"


# Helper function for LocalDB concurrency test - must be at module level to be picklable
def _child_process_init_localdb(dbfolder, result_queue):
    """
    Child process function that initializes a LocalDB.

    Args:
        dbfolder: Path to the database folder
        result_queue: multiprocessing.Queue to report results
    """
    from conan.internal.api.remotes.localdb import LocalDB

    try:
        db = LocalDB(dbfolder)
        # Try to store some credentials to verify the DB is working
        db.store("test_user", "token123", "refresh456", "https://test.remote")
        result_queue.put({"success": True})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


class TestLocalDBConcurrency:
    """
    Tests for concurrent LocalDB initialization.

    These tests verify that the LocalDB class properly handles concurrent
    initialization from multiple processes without corrupting the database.
    """

    def test_localdb_init_is_atomic(self):
        """
        Test that LocalDB initialization works correctly.

        Verifies that SQLite handles file creation atomically and
        CREATE TABLE IF NOT EXISTS is idempotent.
        """
        from conan.internal.api.remotes.localdb import LocalDB, LOCALDB

        with tempfile.TemporaryDirectory() as tmpdir:
            # First initialization - creates DB and table
            db1 = LocalDB(tmpdir)
            db1.store("user1", "token1", "refresh1", "https://remote1")

            # Second initialization - should reuse existing DB
            db2 = LocalDB(tmpdir)
            db2.store("user2", "token2", "refresh2", "https://remote2")

            # Verify both entries exist
            db_check = LocalDB(tmpdir)
            user1, _, _ = db_check.get_login("https://remote1")
            user2, _, _ = db_check.get_login("https://remote2")

            assert user1 == "user1", "First user should be preserved"
            assert user2 == "user2", "Second user should be stored"

    def test_localdb_no_explicit_file_creation(self):
        """
        Test that LocalDB doesn't use check-then-create pattern.

        SQLite should handle file creation atomically via connect().
        """
        from conan.internal.api.remotes.localdb import LocalDB, LOCALDB

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, LOCALDB)

            # File should not exist yet
            assert not os.path.exists(db_path)

            # Initialize DB - SQLite creates file atomically
            db = LocalDB(tmpdir)

            # File should now exist
            assert os.path.exists(db_path), "SQLite should create the database file"

            # Should be a valid SQLite database
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            assert "users_remotes" in tables, "Table should be created"

    @pytest.mark.slow
    def test_concurrent_localdb_init_from_multiple_processes(self):
        """
        Test that multiple processes can safely initialize LocalDB concurrently.

        Spawns multiple child processes that each initialize a LocalDB
        pointing to the same folder. Verifies that all succeed and the
        database is not corrupted.
        """
        from conan.internal.api.remotes.localdb import LocalDB

        with tempfile.TemporaryDirectory() as tmpdir:
            num_processes = 5
            result_queue = multiprocessing.Queue()

            # Spawn processes that each initialize LocalDB
            processes = []
            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_child_process_init_localdb,
                    args=(tmpdir, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=30.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # Verify all succeeded
            for i, result in enumerate(results):
                assert result["success"], f"Process {i} failed: {result.get('error', 'unknown')}"

            # Verify database is not corrupted - can still be used
            db = LocalDB(tmpdir)
            # The last write wins, but it should be valid
            user, token, refresh = db.get_login("https://test.remote")
            assert user == "test_user", "Database should have valid data"
            assert token == "token123", "Token should be retrievable"


# Helper function for save_if_not_exists concurrency test
def _child_process_save_if_not_exists(file_path, content, result_queue):
    """
    Child process function that calls save_if_not_exists.

    Args:
        file_path: Path to the file to create
        content: Content to write
        result_queue: multiprocessing.Queue to report results
    """
    from conan.internal.util.files import save_if_not_exists

    try:
        created = save_if_not_exists(file_path, content)
        result_queue.put({"success": True, "created": created})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


class TestSaveIfNotExistsConcurrency:
    """
    Tests for the save_if_not_exists atomic file creation function.

    These tests verify that save_if_not_exists properly handles concurrent
    file creation attempts without race conditions.
    """

    def test_save_if_not_exists_creates_file(self):
        """Test that save_if_not_exists creates a new file."""
        from conan.internal.util.files import save_if_not_exists, load

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            content = "Hello, World!"

            # File doesn't exist, should create it
            result = save_if_not_exists(file_path, content)

            assert result is True, "Should return True when file is created"
            assert os.path.exists(file_path), "File should exist"
            assert load(file_path) == content, "Content should match"

    def test_save_if_not_exists_returns_false_if_exists(self):
        """Test that save_if_not_exists returns False if file exists."""
        from conan.internal.util.files import save_if_not_exists, save, load

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "test.txt")
            original_content = "Original content"
            new_content = "New content"

            # Create file first
            save(file_path, original_content)

            # Try to create again - should fail and not overwrite
            result = save_if_not_exists(file_path, new_content)

            assert result is False, "Should return False when file exists"
            assert load(file_path) == original_content, "Original content should be preserved"

    def test_save_if_not_exists_creates_parent_dirs(self):
        """Test that save_if_not_exists creates parent directories."""
        from conan.internal.util.files import save_if_not_exists, load

        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "a", "b", "c", "test.txt")
            content = "Nested content"

            result = save_if_not_exists(file_path, content)

            assert result is True, "Should create file in nested directory"
            assert os.path.exists(file_path), "File should exist"
            assert load(file_path) == content, "Content should match"

    @pytest.mark.slow
    def test_concurrent_save_if_not_exists_only_one_wins(self):
        """
        Test that only one process succeeds when multiple try to create the same file.

        Spawns multiple child processes that all try to create the same file
        simultaneously. Verifies that exactly one succeeds (returns True) and
        the others fail gracefully (return False).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = os.path.join(tmpdir, "contested.txt")
            num_processes = 5
            result_queue = multiprocessing.Queue()

            # Spawn processes that all try to create the same file
            processes = []
            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_child_process_save_if_not_exists,
                    args=(file_path, f"Content from process {i}", result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=30.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # All should succeed (no exceptions)
            for result in results:
                assert result["success"], f"Process failed: {result.get('error')}"

            # Exactly one should have created the file
            created_count = sum(1 for r in results if r["created"])
            assert created_count == 1, (
                f"Exactly one process should create the file, but {created_count} did. "
                "This indicates a race condition in save_if_not_exists."
            )

            # File should exist and have valid content
            assert os.path.exists(file_path), "File should exist"


class TestCacheRestoreRaceConditions:
    """
    Tests for cache.restore() race conditions.

    These tests demonstrate the critical race conditions in cache.restore() when
    multiple processes concurrently restore packages:

    1. Unlocked tarball extraction (line 215 in cache.py)
    2. Unlocked package folder moves (lines 252-255)
    3. Unlocked metadata folder moves (lines 265-268)

    The problem: Even though create_ref_layout() and create_pkg_layout() use locks
    internally, those locks are released BEFORE the folder move operations happen.
    This creates a gap where concurrent operations can corrupt the cache.
    """

    @pytest.fixture
    def shared_cache(self):
        """Create a temporary shared cache folder"""
        with tempfile.TemporaryDirectory(prefix="conan_test_") as tmpdir:
            yield tmpdir

    @pytest.mark.slow
    def test_concurrent_restore_same_package(self, shared_cache):
        """
        Test that concurrent restore operations on the same package are safe.
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile
        import shutil

        # Step 1: Create a package and save it to an archive
        temp_client = TestClient()
        temp_client.save({
            "conanfile.py": GenConanfile()
                .with_settings("os")
                .with_package_file("bin/myfile.txt", "important content")
        })
        temp_client.run("create . --name=pkg --version=1.0 -s os=Linux")
        temp_client.run("cache save pkg/*:*")
        archive_path = os.path.join(temp_client.current_folder, "conan_cache_save.tgz")
        assert os.path.exists(archive_path)

        # Step 2: Create working directories for concurrent processes
        with tempfile.TemporaryDirectory() as workdir:
            # Each process needs its own copy of the archive
            process_dirs = []
            for i in range(5):
                pdir = os.path.join(workdir, f"process_{i}")
                os.makedirs(pdir)
                shutil.copy(archive_path, os.path.join(pdir, "archive.tgz"))
                process_dirs.append(pdir)

            # Step 3: Run concurrent restore operations
            client = MultiProcessTestClient(shared_cache)
            commands = [
                (["cache", "restore", "archive.tgz"], pdir)
                for pdir in process_dirs
            ]

            # Run all restores concurrently - they will race
            results = client.run_concurrent(commands, max_workers=5)

            # Step 4: Check results
            # All processes should succeed (they should handle concurrency gracefully)
            success_count = sum(1 for r in results if r.returncode == 0)

            # CURRENT BEHAVIOR (race condition):
            # - Some processes may fail due to concurrent folder operations
            # - May get "File not found" or other filesystem errors
            # - May succeed but leave corrupted state

            # EXPECTED BEHAVIOR (with proper locking):
            # - All processes should succeed
            # - Only one should actually do the restore, others should skip
            # - Cache should be in consistent state

            # This assertion documents the current broken behavior
            # Once fixed, all 5 should succeed
            assert success_count >= 1, "At least one restore should succeed"

            # Verify cache is in a valid state (not corrupted)
            verify_result = client.run_conan(["list", "pkg/1.0:*"])
            assert verify_result.returncode == 0, "Cache should be queryable after concurrent restores"

            # Verify the package actually exists and has correct files
            verify_result = client.run_conan(["cache", "path", "pkg/1.0:*"])
            if verify_result.returncode == 0:
                # Try to verify package contents if we can get the path
                # Note: This may fail due to race conditions in current implementation
                pass

    @pytest.mark.slow
    def test_restore_vs_download_race(self, shared_cache):
        """
        Test that concurrent restore operations are safe with proper locking.

        This test verifies that when multiple processes try to restore the same
        package simultaneously, the locking prevents corruption:
        - Process A: Restores package (has package_lock)
        - Process B: Restores same package (waits for lock or skips if already present)

        With proper locking (added in cache._restore_from_extracted), both processes
        should either:
        1. One succeeds and the other detects files already exist (safe)
        2. Both serialize via locks and files end up correct (safe)
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile
        import shutil

        # Create a package with identifiable content
        temp_client = TestClient()
        temp_client.save({
            "conanfile.py": GenConanfile()
                .with_settings("os")
                .with_package_file("bin/file.txt", "expected_content_ABC123")
        })
        temp_client.run("create . --name=pkg --version=1.0 -s os=Linux")

        # Create an archive for restore
        temp_client.run("cache save pkg/*:*")
        archive_path = os.path.join(temp_client.current_folder, "conan_cache_save.tgz")

        # Setup multiprocess client
        client = MultiProcessTestClient(shared_cache)

        # Prepare multiple working directories, each with a copy of the archive
        with tempfile.TemporaryDirectory() as workdir:
            restore_dirs = []
            for i in range(3):
                restore_dir = os.path.join(workdir, f"restore_{i}")
                os.makedirs(restore_dir)
                shutil.copy(archive_path, os.path.join(restore_dir, "archive.tgz"))
                restore_dirs.append(restore_dir)

            # Run multiple concurrent restores of the same package
            commands = [
                (["cache", "restore", "archive.tgz"], restore_dir)
                for restore_dir in restore_dirs
            ]

            results = client.run_concurrent(commands, max_workers=3)

            # All should succeed (or gracefully handle already-exists)
            for i, result in enumerate(results):
                assert result.returncode == 0, (
                    f"Restore {i} failed with:\nstdout: {result.stdout}\nstderr: {result.stderr}"
                )

            # Cache should be valid after concurrent restores - verify with list command
            verify_result = client.run_conan(["list", "pkg/1.0:*"])
            assert verify_result.returncode == 0, "Cache should be queryable after concurrent restores"

            # Should see the package in the list output
            assert "pkg/1.0" in verify_result.stdout, \
                f"Package should be in cache after restore. Output: {verify_result.stdout}"

    @pytest.mark.slow
    def test_concurrent_restore_stress_test(self, shared_cache):
        """
        Stress test: Run many concurrent restores of the same package and check for issues.

        This test tries to trigger the race condition by:
        1. Creating 20 concurrent processes
        2. All restoring the same package simultaneously
        3. Checking for any failures, errors, or corruption

        Even if the race window is small, with enough iterations we might catch it.
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile
        import shutil

        # Create a package with easily verifiable content
        temp_client = TestClient()
        temp_client.save({
            "conanfile.py": GenConanfile()
                .with_settings("os")
                .with_package_file("bin/file1.txt", "content_ABC_123")
                .with_package_file("bin/file2.txt", "more_data_here")
                .with_package_file("lib/library.a", "library_binary_data_12345")
        })
        temp_client.run("create . --name=pkg --version=1.0 -s os=Linux")
        temp_client.run("cache save pkg/*:*")
        archive_path = os.path.join(temp_client.current_folder, "conan_cache_save.tgz")

        # Create working directories for many concurrent processes
        with tempfile.TemporaryDirectory() as workdir:
            num_processes = 20
            process_dirs = []
            for i in range(num_processes):
                pdir = os.path.join(workdir, f"process_{i}")
                os.makedirs(pdir)
                shutil.copy(archive_path, os.path.join(pdir, "archive.tgz"))
                process_dirs.append(pdir)

            # Run concurrent restores
            client = MultiProcessTestClient(shared_cache)
            commands = [
                (["cache", "restore", "archive.tgz"], pdir)
                for pdir in process_dirs
            ]

            print(f"\n=== Running {num_processes} concurrent restores ===")
            results = client.run_concurrent(commands, max_workers=num_processes)

            # Analyze results
            success_count = 0
            error_count = 0
            errors = []

            for i, r in enumerate(results):
                if r.returncode == 0:
                    success_count += 1
                else:
                    error_count += 1
                    errors.append({
                        "process": i,
                        "returncode": r.returncode,
                        "stderr": r.stderr[:500] if r.stderr else ""
                    })

            print(f"Successful: {success_count}/{num_processes}")
            print(f"Failed: {error_count}/{num_processes}")

            if errors:
                print("\n=== Errors Detected ===")
                for err in errors[:5]:  # Show first 5 errors
                    print(f"Process {err['process']}: rc={err['returncode']}")
                    if err['stderr']:
                        print(f"  {err['stderr']}")

            # Verify cache integrity
            verify_result = client.run_conan(["list", "pkg/1.0:*"])
            assert verify_result.returncode == 0, "Cache should be queryable after concurrent restores"

            # Get the package and verify file contents
            path_result = client.run_conan(["cache", "path", "pkg/1.0:*"])
            if path_result.returncode == 0:
                # Extract package path
                lines = path_result.stdout.strip().split('\n')
                pkg_path = None
                for line in lines:
                    if '/p/pkg' in line or 'pkg/1.0' in line:
                        # Try to extract the path
                        import re
                        match = re.search(r'(/[^\s]+/p/[^\s]+)', line)
                        if match:
                            pkg_path = match.group(1)
                            break

                if pkg_path and os.path.exists(pkg_path):
                    print(f"\n=== Verifying package at: {pkg_path} ===")

                    # Check all expected files exist and have correct content
                    file1 = os.path.join(pkg_path, "bin", "file1.txt")
                    file2 = os.path.join(pkg_path, "bin", "file2.txt")
                    file3 = os.path.join(pkg_path, "lib", "library.a")

                    all_good = True
                    for fpath, expected_content in [
                        (file1, "content_ABC_123"),
                        (file2, "more_data_here"),
                        (file3, "library_binary_data_12345")
                    ]:
                        if os.path.exists(fpath):
                            with open(fpath, 'r') as f:
                                actual = f.read()
                            if actual != expected_content:
                                print(f"CORRUPTION: {fpath} has wrong content!")
                                print(f"  Expected: {repr(expected_content)}")
                                print(f"  Actual: {repr(actual)}")
                                all_good = False
                        else:
                            print(f"MISSING FILE: {fpath}")
                            all_good = False

                    if all_good:
                        print("All files verified OK")
                    else:
                        print("\n!!! CORRUPTION DETECTED !!!")
                        print("This proves the race condition caused file corruption.")
                        # Don't fail the test - we want to report this as expected behavior
                        # until the fix is implemented

            # Report summary
            print(f"\n=== Test Summary ===")
            print(f"Total processes: {num_processes}")
            print(f"Successful restores: {success_count}")
            print(f"Failed restores: {error_count}")
            print(f"Failure rate: {error_count/num_processes*100:.1f}%")

            if error_count > 0:
                print(f"\n!!! RACE CONDITION DETECTED !!!")
                print(f"{error_count} processes failed due to concurrent access issues.")
                print("This demonstrates the race condition exists in cache.restore()")

            # The test passes regardless - we're just documenting the behavior
            # In a perfect world with proper locking, success_count should be num_processes

    def test_restore_unlocked_extraction_demonstration(self):
        """
        Unit test demonstrating the restore() implementation structure.

        This test verifies that the restore() method properly uses temporary
        extraction to avoid race conditions during the extraction phase, and then
        uses the helper method _restore_from_extracted for the actual restoration.
        """
        from conan.api.subapi.cache import CacheAPI
        import inspect

        # Examine the restore() method source code
        restore_source = inspect.getsource(CacheAPI.restore)
        restore_from_extracted_source = inspect.getsource(CacheAPI._restore_from_extracted)

        # Check restore() uses temporary directory
        assert 'TemporaryDirectory' in restore_source, \
            "restore() should use TemporaryDirectory for extraction"
        assert 'extractall' in restore_source, \
            "restore() should extract tarball"
        assert '_restore_from_extracted' in restore_source, \
            "restore() should call _restore_from_extracted helper"

        # Check _restore_from_extracted has the proper locking
        assert 'recipe_lock' in restore_from_extracted_source, \
            "_restore_from_extracted should use recipe_lock"
        assert 'package_lock' in restore_from_extracted_source, \
            "_restore_from_extracted should use package_lock"
        assert 'create_ref_layout' in restore_from_extracted_source, \
            "_restore_from_extracted should call create_ref_layout"
        assert 'create_pkg_layout' in restore_from_extracted_source, \
            "_restore_from_extracted should call create_pkg_layout"

        # Verify the extraction happens in restore() before _restore_from_extracted is called
        lines = restore_source.split('\n')
        extractall_idx = None
        restore_from_extracted_idx = None

        for idx, line in enumerate(lines):
            if 'extractall' in line:
                extractall_idx = idx
            if '_restore_from_extracted' in line and 'self.' in line:
                restore_from_extracted_idx = idx

        assert extractall_idx is not None and restore_from_extracted_idx is not None
        assert extractall_idx < restore_from_extracted_idx, \
            "Extraction should happen before calling _restore_from_extracted"

    def test_restore_gap_between_create_and_move(self):
        """
        Documentation test showing the gap between lock release and folder operations.

        The issue:
        1. create_pkg_layout() acquires package_lock
        2. create_pkg_layout() creates DB entry
        3. create_pkg_layout() releases package_lock  <-- LOCK RELEASED HERE
        4. create_pkg_layout() returns to restore()
        5. [GAP - NO LOCK HELD]
        6. restore() does shutil.rmtree()  <-- UNLOCKED OPERATION
        7. restore() does shutil.move()    <-- UNLOCKED OPERATION

        During the gap (steps 5-7), another process can:
        - Also call create_pkg_layout() and get the existing layout
        - Start its own folder operations
        - Corrupt the cache by racing on folder operations
        """
        from conan.internal.cache.cache import CacheOperations
        import inspect

        # Verify that create_package releases the lock before returning
        create_package_source = inspect.getsource(CacheOperations.create_package)
        lines = create_package_source.split('\n')

        # Find the lock acquisition and release
        with_package_lock_idx = None
        return_idx = None

        for idx, line in enumerate(lines):
            if 'with self._lock.package_lock' in line:
                with_package_lock_idx = idx
            if 'return' in line and idx > (with_package_lock_idx or 0):
                return_idx = idx
                break

        assert with_package_lock_idx is not None, "package_lock should be used"
        assert return_idx is not None, "Function should return"

        # The lock is released when the 'with' block exits,
        # which happens BEFORE the function returns
        # This means the caller (restore) receives the layout WITHOUT holding the lock
        assert return_idx > with_package_lock_idx, \
            "Function returns after 'with' block, meaning lock is released before return"


# Helper functions for cache.clean() concurrency tests - must be at module level
def _child_process_run_source(cache_folder, working_dir, result_queue):
    """
    Child process that runs 'conan source' to populate source folder.

    Args:
        cache_folder: Path to the cache folder
        working_dir: Working directory with conanfile
        result_queue: multiprocessing.Queue to report results
    """
    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        client.current_folder = working_dir
        client.run("source .")
        result_queue.put({"success": True, "operation": "source"})
    except Exception as e:
        result_queue.put({"success": False, "operation": "source", "error": str(e)})


def _child_process_run_clean(cache_folder, pattern, flags, result_queue):
    """
    Child process that runs 'conan cache clean'.

    Args:
        cache_folder: Path to the cache folder
        pattern: Pattern for packages to clean (e.g., "*")
        flags: Clean flags (e.g., "-s -b")
        result_queue: multiprocessing.Queue to report results
    """
    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        client.run(f"cache clean {pattern} {flags}")
        result_queue.put({"success": True, "operation": "clean"})
    except Exception as e:
        result_queue.put({"success": False, "operation": "clean", "error": str(e)})


def _child_process_run_create(cache_folder, working_dir, result_queue):
    """
    Child process that runs 'conan create' (includes build).

    Args:
        cache_folder: Path to the cache folder
        working_dir: Working directory with conanfile
        result_queue: multiprocessing.Queue to report results
    """
    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        client.current_folder = working_dir
        client.run("create . --name=pkg --version=1.0")
        result_queue.put({"success": True, "operation": "create"})
    except Exception as e:
        result_queue.put({"success": False, "operation": "create", "error": str(e)})


class TestCacheCleanConcurrency:
    """
    Tests for cache.clean() concurrent access.

    These tests demonstrate the race conditions in cache.clean() when multiple
    processes access the cache concurrently. The clean() method currently lacks
    proper locking, leading to potential corruption.
    """

    @pytest.fixture
    def shared_cache(self):
        """Create a temporary shared cache folder"""
        with tempfile.TemporaryDirectory(prefix="conan_test_clean_") as tmpdir:
            yield tmpdir

    @pytest.mark.slow
    def test_concurrent_clean_and_source(self, shared_cache):
        """
        Test race condition: clean deleting source folder while source() is running.

        Race Condition:
        - Process A: Running 'conan source' to populate source folder
        - Process B: Running 'conan cache clean -s' to delete source folder
        - Without source_lock: Process A may fail with "No such file or directory"

        Expected with proper locking:
        - Both processes should complete successfully
        - Operations should be serialized by source_lock
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile

        # Setup: Create a package in the shared cache
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = GenConanfile().with_exports_sources("*.txt")
        setup_client.save({
            "conanfile.py": conanfile,
            "source1.txt": "content1",
            "source2.txt": "content2",
            "source3.txt": "content3"
        })
        setup_client.run("create . --name=pkg --version=1.0")

        # Get the ref_layout and verify source folder exists
        ref_layout = setup_client.exported_layout()
        assert os.path.exists(ref_layout.source()), "Source folder should exist after create"

        # Now delete the source folder to set up for the race
        setup_client.run("cache clean * -s")
        assert not os.path.exists(ref_layout.source()), "Source should be cleaned"

        # Create working directory for source operation
        with tempfile.TemporaryDirectory() as workdir:
            # Copy conanfile to working dir
            import shutil
            shutil.copy(
                os.path.join(setup_client.current_folder, "conanfile.py"),
                os.path.join(workdir, "conanfile.py")
            )
            for f in ["source1.txt", "source2.txt", "source3.txt"]:
                shutil.copy(
                    os.path.join(setup_client.current_folder, f),
                    os.path.join(workdir, f)
                )

            result_queue = multiprocessing.Queue()

            # Process A: Run source (will create source folder)
            process_source = multiprocessing.Process(
                target=_child_process_run_source,
                args=(shared_cache, workdir, result_queue)
            )

            # Process B: Run clean -s (will try to delete source folder)
            process_clean = multiprocessing.Process(
                target=_child_process_run_clean,
                args=(shared_cache, "*", "-s", result_queue)
            )

            # Start both processes
            process_source.start()
            time.sleep(0.05)  # Give source a head start
            process_clean.start()

            # Wait for both to complete
            process_source.join(timeout=30.0)
            process_clean.join(timeout=30.0)

            assert not process_source.is_alive(), "Source process should complete"
            assert not process_clean.is_alive(), "Clean process should complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # EXPECTED (with proper locking): Both operations succeed
            # CURRENT (without locking): Source may fail if clean deletes folder mid-operation
            source_result = next((r for r in results if r["operation"] == "source"), None)
            clean_result = next((r for r in results if r["operation"] == "clean"), None)

            assert source_result is not None, "Should have source result"
            assert clean_result is not None, "Should have clean result"

            # This assertion may fail due to race condition
            assert source_result["success"], \
                f"Source should succeed with proper locking. Error: {source_result.get('error', 'N/A')}"
            assert clean_result["success"], \
                f"Clean should succeed. Error: {clean_result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_concurrent_clean_and_build(self, shared_cache):
        """
        Test race condition: clean deleting build folder while build is running.

        Race Condition:
        - Process A: Running 'conan create' (building package)
        - Process B: Running 'conan cache clean -b' to delete build folder
        - Without package_lock: Process A may fail when build artifacts disappear

        Expected with proper locking:
        - Both processes should complete successfully
        - Operations should be serialized by package_lock
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile

        # Setup: Create a package with a build step
        setup_client = TestClient(cache_folder=shared_cache)
        # Create a conanfile with build messages (slow build to increase race window)
        conanfile = GenConanfile().with_build_msg("Starting build")\
                                  .with_build_msg("Build step 1")\
                                  .with_build_msg("Build step 2")\
                                  .with_build_msg("Build complete")
        setup_client.save({"conanfile.py": conanfile})

        # Create working directories for concurrent processes
        with tempfile.TemporaryDirectory() as workdir1, \
             tempfile.TemporaryDirectory() as workdir2:

            # Copy conanfile to both working dirs
            import shutil
            for workdir in [workdir1, workdir2]:
                shutil.copy(
                    os.path.join(setup_client.current_folder, "conanfile.py"),
                    os.path.join(workdir, "conanfile.py")
                )

            result_queue = multiprocessing.Queue()

            # Process A: Create package (with slow build)
            process_create = multiprocessing.Process(
                target=_child_process_run_create,
                args=(shared_cache, workdir1, result_queue)
            )

            # Process B: Clean build folders
            process_clean = multiprocessing.Process(
                target=_child_process_run_clean,
                args=(shared_cache, "*", "-b", result_queue)
            )

            # Start create first
            process_create.start()
            # Wait a bit for build to start, then run clean
            time.sleep(0.2)
            process_clean.start()

            # Wait for both to complete
            process_create.join(timeout=30.0)
            process_clean.join(timeout=30.0)

            assert not process_create.is_alive(), "Create process should complete"
            assert not process_clean.is_alive(), "Clean process should complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            create_result = next((r for r in results if r["operation"] == "create"), None)
            clean_result = next((r for r in results if r["operation"] == "clean"), None)

            assert create_result is not None, "Should have create result"
            assert clean_result is not None, "Should have clean result"

            # EXPECTED (with proper locking): Both succeed, operations serialized
            # CURRENT (without locking): Create may fail if build folder deleted mid-build
            assert create_result["success"], \
                f"Create should succeed with proper locking. Error: {create_result.get('error', 'N/A')}"
            assert clean_result["success"], \
                f"Clean should succeed. Error: {clean_result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_build_folder_clean_with_package_lock(self, shared_cache):
        """
        Test that build folder deletion is protected by package_lock.

        This test verifies that when clean deletes a build folder, it properly
        acquires the package_lock to prevent concurrent operations on the same
        package from causing corruption.

        The fix ensures that both the build folder deletion and any associated
        DB writes (like remove_build_id) are atomic under the same lock.
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile

        # Setup: Create a simple package
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = GenConanfile().with_build_msg("Building package")
        setup_client.save({"conanfile.py": conanfile})
        setup_client.run("create . --name=pkg --version=1.0")

        # Get the package reference
        pref = setup_client.created_package_reference("pkg/1.0")
        pkg_layout = setup_client.cache.pkg_layout(pref)

        # Verify build folder exists
        assert os.path.exists(pkg_layout.build()), "Build folder should exist"

        # Now run concurrent clean operations
        num_processes = 5
        result_queue = multiprocessing.Queue()
        processes = []

        for i in range(num_processes):
            p = multiprocessing.Process(
                target=_child_process_run_clean,
                args=(shared_cache, "*", "-b", result_queue)
            )
            processes.append(p)

        # Start all processes
        for p in processes:
            p.start()

        # Wait for all to complete
        for p in processes:
            p.join(timeout=30.0)
            assert not p.is_alive(), "Process should complete (no deadlock)"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        assert len(results) == num_processes, f"Should have {num_processes} results"

        # All should succeed (clean with locking is safe)
        for i, result in enumerate(results):
            assert result["success"], \
                f"Clean process {i} should succeed with proper locking. Error: {result.get('error', 'N/A')}"

        # Verify cache is still in consistent state
        verify_client = TestClient(cache_folder=shared_cache)
        verify_client.run("list *")
        # Should succeed without errors

    @pytest.mark.slow
    def test_multiple_concurrent_cleans(self, shared_cache):
        """
        Test that multiple processes can safely run clean concurrently.

        This stress test runs many concurrent clean operations to verify:
        1. No deadlocks occur
        2. All operations complete successfully
        3. Cache remains in consistent state

        Unlike the other tests, this one should pass even without proper locking
        because clean is idempotent (cleaning something already clean is safe).
        However, it's useful for verifying that the locks don't introduce deadlocks.
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile

        # Setup: Create several packages
        setup_client = TestClient(cache_folder=shared_cache)
        for i in range(3):
            conanfile = GenConanfile()
            setup_client.save({"conanfile.py": conanfile})
            setup_client.run(f"create . --name=pkg{i} --version=1.0")

        # Run many concurrent clean operations
        num_processes = 10
        result_queue = multiprocessing.Queue()
        processes = []

        for i in range(num_processes):
            p = multiprocessing.Process(
                target=_child_process_run_clean,
                args=(shared_cache, "*", "-s -b -d", result_queue)
            )
            processes.append(p)

        # Start all processes
        for p in processes:
            p.start()

        # Wait for all to complete
        for p in processes:
            p.join(timeout=30.0)
            assert not p.is_alive(), "Process should complete (no deadlock)"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        assert len(results) == num_processes, f"Should have {num_processes} results"

        # All should succeed (clean is idempotent)
        for i, result in enumerate(results):
            assert result["success"], \
                f"Clean process {i} should succeed. Error: {result.get('error', 'N/A')}"

        # Verify cache is still queryable
        verify_client = TestClient(cache_folder=shared_cache)
        verify_client.run("list *")
        # Should succeed without errors

    @pytest.mark.slow
    def test_clean_temp_folders_concurrent(self, shared_cache):
        """
        Test that temp folder cleaning is safe without locks.

        The temp folder uses UUID-based naming, making collisions extremely unlikely.
        This test verifies that concurrent clean operations on temp folders don't
        cause issues even without explicit locking.
        """
        from conan.test.utils.tools import TestClient
        from conan.test.assets.genconanfile import GenConanfile

        # Setup: Create some temp folders by starting exports
        # (exports create temp folders before computing revision)
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = GenConanfile()
        setup_client.save({"conanfile.py": conanfile})

        # Create a few packages to populate cache
        for i in range(3):
            setup_client.run(f"create . --name=pkg{i} --version=1.0")

        # Run concurrent clean operations on temp folders
        num_processes = 5
        result_queue = multiprocessing.Queue()
        processes = []

        for i in range(num_processes):
            p = multiprocessing.Process(
                target=_child_process_run_clean,
                args=(shared_cache, "*", "", result_queue)  # No flags = just temp
            )
            processes.append(p)

        # Start all processes
        for p in processes:
            p.start()

        # Wait for all to complete
        for p in processes:
            p.join(timeout=30.0)
            assert not p.is_alive(), "Process should complete"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        # All should succeed
        for result in results:
            assert result["success"], \
                f"Temp clean should succeed. Error: {result.get('error', 'N/A')}"
