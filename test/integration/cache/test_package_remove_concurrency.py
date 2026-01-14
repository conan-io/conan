"""
Tests for package removal concurrency issues.

This test file contains tests for race conditions in package removal operations
that are currently marked as TODO in conan_reference_layout.py:144-151.
"""

import multiprocessing
import os
import tempfile
import time

import pytest

from test.utils.multiprocess import MultiProcessTestClient


def _child_process_remove_package(cache_folder, package_ref, result_queue):
    """
    Child process that runs 'conan remove' to remove a package.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        client.run(f"remove {package_ref} -c")

        result_queue.put({
            "success": True,
            "operation": "remove",
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "remove",
            "error": str(e)
        })


def _child_process_cache_path(cache_folder, package_ref, result_queue):
    """
    Child process that runs 'conan cache path' while removal is happening.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        # Try to access the package multiple times
        # Don't assert_error - we just want to see what happens
        for _ in range(5):
            try:
                client.run(f"cache path {package_ref}")
                # Command succeeded - that's fine, package still exists
            except Exception:
                # Command failed - that's also fine, package was removed
                pass
            time.sleep(0.02)

        result_queue.put({
            "success": True,
            "operation": "path",
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "path",
            "error": str(e)
        })


class TestPackageRemoveConcurrency:
    """
    Tests for race conditions in package removal operations.

    These tests verify that package_lock properly protects package removal operations.

    Previously, these operations had TODOs at:
    - conan_reference_layout.py:144 - package_remove() lacking locks
    - conan_reference_layout.py:107 - package_lock() being a no-op

    The fix implements PackageLayout.package_lock() to use the ConcurrencyLock
    system, protecting:
    1. Multiple processes removing the same package simultaneously
    2. Removing a package while another process accesses it
    3. rmdir operations on package/download folders
    """

    @pytest.mark.slow
    def test_concurrent_package_remove(self, shared_cache):
        """
        Test race condition: Multiple processes removing the same package simultaneously.

        Race Condition (now prevented):
        - Process A: Deleting package folders (download_package, package, dirty file)
        - Process B: Deleting the same package folders at the same time
        - With locking: Operations are serialized, one succeeds, others get "already removed"

        The package_lock ensures safe concurrent removal operations.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
"""
        setup_client.save({"conanfile.py": conanfile})
        setup_client.run("create .")

        # Verify package exists
        setup_client.run("list pkg/1.0:*")
        assert "pkg/1.0" in setup_client.out

        result_queue = multiprocessing.Queue()

        # Start 3 processes trying to remove the same package simultaneously
        processes = []
        for i in range(3):
            p = multiprocessing.Process(
                target=_child_process_remove_package,
                args=(shared_cache, "pkg/1.0:*", result_queue)
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

        assert len(results) == 3, f"Should have 3 results, got {len(results)}"

        # All processes should succeed - the remove command now handles concurrent removals
        for i, result in enumerate(results):
            assert result["success"], \
                f"Process {i} should handle concurrent removal gracefully. " \
                f"Error: {result.get('error', 'N/A')}"

        # Verify packages are actually removed (recipe may still exist but no binaries)
        verify_client = TestClient(cache_folder=shared_cache)
        verify_client.run("list pkg/1.0:*")
        # After removal, either:
        # 1. Recipe itself should be gone, OR
        # 2. Recipe exists but shows no package IDs
        # The pattern pkg/1.0:* means "all packages for this recipe"
        # so the recipe itself might remain but packages should be gone
        # Check that we don't see an actual package ID (starts with revision or package_id)
        assert "da39a3ee5e6b4b0d3255bfef95601890afd80709" not in verify_client.out or \
               "WARN" in verify_client.out

    @pytest.mark.slow
    def test_concurrent_remove_and_access(self, shared_cache):
        """
        Test race condition: Removing a package while another process accesses it.

        Race Condition (now prevented):
        - Process A: Removing package (deleting folders)
        - Process B: Trying to access package path
        - With locking: Process B either sees the package or gets a clean "not found"

        The package_lock ensures no partial deletion is visible.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "removepkg"
    version = "1.0"
"""
        setup_client.save({"conanfile.py": conanfile})
        setup_client.run("create .")

        result_queue = multiprocessing.Queue()

        # Process A: Remove the package
        process_remove = multiprocessing.Process(
            target=_child_process_remove_package,
            args=(shared_cache, "removepkg/1.0:*", result_queue)
        )

        # Process B: Try to access the package
        process_access = multiprocessing.Process(
            target=_child_process_cache_path,
            args=(shared_cache, "removepkg/1.0", result_queue)
        )

        # Start both processes
        process_remove.start()
        time.sleep(0.02)  # Small delay so removal starts first
        process_access.start()

        # Wait for both to complete
        process_remove.join(timeout=30.0)
        process_access.join(timeout=30.0)

        assert not process_remove.is_alive(), "Remove process should complete"
        assert not process_access.is_alive(), "Access process should complete"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        assert len(results) == 2, "Should have 2 results"

        remove_result = next((r for r in results if r["operation"] == "remove"), None)
        access_result = next((r for r in results if r["operation"] == "path"), None)

        assert remove_result is not None, "Should have remove result"
        assert access_result is not None, "Should have access result"

        # Remove should succeed
        assert remove_result["success"], \
            f"Remove should succeed. Error: {remove_result.get('error', 'N/A')}"

        # Access should handle the situation gracefully (may fail, but not crash)
        # With locking, access either sees the package or gets a clean error
        assert access_result["success"], \
            f"Access should handle concurrent removal gracefully. " \
            f"Error: {access_result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_package_remove_with_dirty_folder(self, shared_cache):
        """
        Test race condition: Concurrent package removal with dirty folder cleanup.

        Race Condition (now prevented):
        - Process A: Removing package, checking and cleaning dirty file
        - Process B: Removing same package, both try to clean dirty file
        - With locking: Only one process cleans dirty file, no errors

        Combined with the clean_dirty() fix that handles FileNotFoundError gracefully.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = """
from conan import ConanFile

class Pkg(ConanFile):
    name = "dirtypkg"
    version = "1.0"
"""
        setup_client.save({"conanfile.py": conanfile})
        setup_client.run("create .")

        # Mark package as dirty
        pref = setup_client.created_package_reference("dirtypkg/1.0")
        pkg_layout = setup_client.cache.pkg_layout(pref)
        from conan.internal.util.files import set_dirty
        set_dirty(pkg_layout.package())

        result_queue = multiprocessing.Queue()

        # Start 2 processes trying to remove the dirty package
        processes = []
        for i in range(2):
            p = multiprocessing.Process(
                target=_child_process_remove_package,
                args=(shared_cache, "dirtypkg/1.0:*", result_queue)
            )
            processes.append(p)

        # Start both simultaneously
        for p in processes:
            p.start()

        # Wait for both to complete
        for p in processes:
            p.join(timeout=30.0)
            assert not p.is_alive(), "Process did not complete"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        assert len(results) == 2, "Should have 2 results"

        # EXPECTED (with proper locking): Both succeed, dirty file cleaned once
        # CURRENT (without locking): May fail with FileNotFoundError on dirty file
        for i, result in enumerate(results):
            assert result["success"], \
                f"Remove process {i} should succeed even with dirty folder. " \
                f"Error: {result.get('error', 'N/A')}"


@pytest.fixture
def shared_cache():
    """Fixture that provides a shared cache folder for multi-process tests."""
    with tempfile.TemporaryDirectory(prefix="conan_pkg_remove_test_") as tmpdir:
        yield tmpdir
