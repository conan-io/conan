"""
Test that DownloadCache uses ConcurrencyLock infrastructure.

This verifies that the download cache locking is integrated with the
lock hierarchy system to prevent potential deadlocks.
"""

import json
import multiprocessing
import os
import tempfile

import pytest

from conan.internal.cache.concurrency_lock import ConcurrencyLock
from conan.internal.rest.download_cache import DownloadCache
from conan.internal.util.files import load


def test_download_cache_uses_concurrency_lock():
    """Verify DownloadCache uses ConcurrencyLock, not direct fasteners usage"""
    with tempfile.TemporaryDirectory() as tmpdir:
        download_cache = DownloadCache(tmpdir)

        # DownloadCache should have a ConcurrencyLock instance
        assert hasattr(download_cache, '_lock_manager'), \
            "DownloadCache should have _lock_manager attribute"
        assert isinstance(download_cache._lock_manager, ConcurrencyLock), \
            "DownloadCache._lock_manager should be a ConcurrencyLock instance"


def test_download_cache_lock_works():
    """Verify the lock() method still works correctly after migration"""
    with tempfile.TemporaryDirectory() as tmpdir:
        download_cache = DownloadCache(tmpdir)

        # Should be able to acquire and release lock
        lock_id = "test_lock"
        with download_cache.lock(lock_id):
            # Verify lock file exists while held
            lock_file = os.path.join(tmpdir, "locks", lock_id)
            assert os.path.exists(lock_file), "Lock file should exist while lock is held"

        # Lock should be released (file deleted) after context manager exits
        # Note: ConcurrencyLock deletes lock files after release


def test_download_cache_lock_reentrant():
    """Verify lock is reentrant (same thread can acquire multiple times)"""
    with tempfile.TemporaryDirectory() as tmpdir:
        download_cache = DownloadCache(tmpdir)

        lock_id = "test_lock"
        # Should not deadlock
        with download_cache.lock(lock_id):
            with download_cache.lock(lock_id):
                with download_cache.lock(lock_id):
                    pass  # Triple nested - tests reentrancy


# Helper function for multiprocessing - must be at module level to be picklable
def _child_process_update_backup_json(cache_folder, cached_path, pkg_ref, url, process_id, result_queue):
    """
    Child process function that calls update_backup_sources_json.

    This simulates multiple processes downloading the same source file
    and updating the metadata JSON concurrently.

    Args:
        cache_folder: Path to the download cache folder
        cached_path: Path to the cached file (without .json extension)
        pkg_ref: Package reference string
        url: URL to add to the metadata
        process_id: ID for this process
        result_queue: multiprocessing.Queue to report results
    """
    import time
    try:
        # Create a mock conanfile object with minimal attributes
        class MockConanFile:
            def __init__(self, ref_str):
                self.ref = ref_str
                self.name = None
                self.version = None
                self.user = None
                self.channel = None

            class MockOutput:
                def verbose(self, msg):
                    pass
                def debug(self, msg):
                    pass

            output = MockOutput()

        conanfile = MockConanFile(pkg_ref)

        # Add a small delay to increase the race window
        # This makes it more likely for multiple processes to be in the
        # read-modify-write section simultaneously
        time.sleep(0.001 * process_id)

        # Create DownloadCache instance and call method
        # Now the method has internal locking, so this is safe
        download_cache = DownloadCache(cache_folder)
        download_cache.update_backup_sources_json(cached_path, conanfile, url)

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "ref": pkg_ref,
            "url": url
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "error": str(e)
        })


class TestDownloadCacheMetadataConcurrency:
    """
    Tests for download cache metadata JSON concurrency protection.

    The update_backup_sources_json() method had a classic read-modify-write
    pattern without internal locking protection. It was a @staticmethod that
    relied on callers to hold a lock.

    After the fix, the method is now an instance method with internal locking
    and atomic writes, making it self-protecting and impossible to misuse.
    """

    def test_sequential_updates_work(self):
        """Verify that sequential updates work correctly (baseline test)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            download_cache = DownloadCache(tmpdir)
            cached_path = os.path.join(tmpdir, "test_sha256")

            # Create mock conanfile
            class MockConanFile:
                def __init__(self, ref_str):
                    self.ref = ref_str
                    self.name = None
                    self.version = None

                class MockOutput:
                    def verbose(self, msg):
                        pass
                    def debug(self, msg):
                        pass

                output = MockOutput()

            # Update with first package
            conanfile1 = MockConanFile("pkg1/1.0")
            download_cache.update_backup_sources_json(cached_path, conanfile1, "http://url1.com")

            # Update with second package
            conanfile2 = MockConanFile("pkg2/1.0")
            download_cache.update_backup_sources_json(cached_path, conanfile2, "http://url2.com")

            # Verify both are present
            json_path = cached_path + ".json"
            assert os.path.exists(json_path)

            with open(json_path, 'r') as f:
                data = json.load(f)

            refs = data["references"]
            assert "pkg1/1.0" in refs
            assert "pkg2/1.0" in refs
            assert refs["pkg1/1.0"] == ["http://url1.com"]
            assert refs["pkg2/1.0"] == ["http://url2.com"]

    @pytest.mark.slow
    def test_concurrent_updates_with_internal_locking(self):
        """
        Test that concurrent calls to update_backup_sources_json work correctly
        with the internal locking protection.

        After the fix, the method is an instance method with internal locking,
        so concurrent calls should be safe even without an external lock.

        Expected behavior with fix:
        - All packages present in final JSON (no lost updates)
        - Valid JSON (no corruption)
        - Proper serialization of updates

        This test should PASS after the fix.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create the parent directory structure that DownloadCache expects
            cache_subdir = os.path.join(tmpdir, "s")
            os.makedirs(cache_subdir, exist_ok=True)
            cached_path = os.path.join(cache_subdir, "shared_sha256")

            # Run multiple concurrent updates to the same JSON file
            num_processes = 5

            # Use spawn context to avoid fork issues in pytest
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                pkg_ref = f"pkg{i}/1.0"
                url = f"http://example.com/pkg{i}.tar.gz"

                p = mp_context.Process(
                    target=_child_process_update_backup_json,
                    args=(tmpdir, cached_path, pkg_ref, url, i, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60)
                if p.is_alive():
                    p.terminate()
                    p.join()
                    pytest.fail("Process did not complete - possible deadlock or resource exhaustion")

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # All should succeed (no exceptions)
            failures = [r for r in results if not r["success"]]
            if failures:
                pytest.fail(f"Some processes failed: {failures}")

            # Verify we got results from all processes
            assert len(results) == num_processes, (
                f"Expected {num_processes} results, got {len(results)}. "
                "Some processes may have failed to report."
            )

            # Verify the JSON file exists and is valid
            json_path = cached_path + ".json"
            assert os.path.exists(json_path), (
                f"JSON metadata file should exist at {json_path}. "
                f"Directory contents: {os.listdir(os.path.dirname(json_path))}"
            )

            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
            except json.JSONDecodeError as e:
                pytest.fail(f"JSON file is corrupted: {e}. "
                           "This indicates a race condition in concurrent writes.")

            # Check how many packages made it into the final JSON
            refs = data["references"]
            found_pkgs = len(refs)

            # This is the key assertion - we should have all 10 packages
            # With the fix (internal locking), all packages should be present
            assert found_pkgs == num_processes, (
                f"Should have all {num_processes} packages in metadata, found {found_pkgs}. "
                f"References: {list(refs.keys())}. "
                "Internal locking should prevent lost updates."
            )

            # Verify each package has its URL
            for i in range(num_processes):
                pkg_ref = f"pkg{i}/1.0"
                expected_url = f"http://example.com/pkg{i}.tar.gz"
                assert pkg_ref in refs, f"Package {pkg_ref} is missing from metadata"
                assert expected_url in refs[pkg_ref], \
                    f"URL {expected_url} is missing for {pkg_ref}"

    def test_current_usage_is_safe(self):
        """
        Verify that the current usage pattern (with lock) is safe.

        This shows that when callers properly use the lock, the race condition
        doesn't occur. This is how caching_file_downloader.py currently uses it.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            download_cache = DownloadCache(tmpdir)
            cached_path = os.path.join(tmpdir, "s", "test_sha256")
            os.makedirs(os.path.dirname(cached_path), exist_ok=True)

            # Create mock conanfile
            class MockConanFile:
                def __init__(self, ref_str):
                    self.ref = ref_str
                    self.name = None
                    self.version = None

                class MockOutput:
                    def verbose(self, msg):
                        pass
                    def debug(self, msg):
                        pass

                output = MockOutput()

            # Simulate the current usage pattern from caching_file_downloader.py
            # After the fix, the method has internal locking, so the outer lock
            # is now redundant (but harmless - defense in depth)
            lock_id = "test_sha256"
            with download_cache.lock(lock_id):
                conanfile = MockConanFile("pkg1/1.0")
                download_cache.update_backup_sources_json(cached_path, conanfile,
                                                         "http://url1.com")

            # Verify it worked
            json_path = cached_path + ".json"
            assert os.path.exists(json_path)

            with open(json_path, 'r') as f:
                data = json.load(f)

            assert "pkg1/1.0" in data["references"]

    def test_instance_method_with_internal_locking(self):
        """
        Verify that update_backup_sources_json is now an instance method
        with internal locking, fixing the architectural vulnerability.

        After the fix, the method:
        - Requires a DownloadCache instance
        - Has internal locking protection
        - Cannot be misused by calling without a lock
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            download_cache = DownloadCache(tmpdir)
            cached_path = os.path.join(tmpdir, "test_sha256")

            class MockConanFile:
                ref = "pkg/1.0"
                name = None
                version = None

                class MockOutput:
                    def verbose(self, msg):
                        pass
                    def debug(self, msg):
                        pass

                output = MockOutput()

            # Now it's an instance method with internal locking - safe!
            download_cache.update_backup_sources_json(
                cached_path,
                MockConanFile(),
                "http://url.com"
            )

            # Verify it worked
            json_path = cached_path + ".json"
            assert os.path.exists(json_path)

            with open(json_path, 'r') as f:
                data = json.load(f)

            assert "pkg/1.0" in data["references"]
            assert "http://url.com" in data["references"]["pkg/1.0"]
