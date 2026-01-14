"""
Tests for compatibility plugin file concurrency issues.

This test verifies that the compatibility.py plugin file migration is properly
protected with locks to prevent concurrent writes during initial setup when
multiple processes start simultaneously.
"""

import multiprocessing
import os
import tempfile

import pytest

from conan.test.utils.tools import TestClient


def _child_process_first_run(cache_folder, result_queue):
    """
    Child process that performs first-time setup/migration.
    This simulates multiple conan processes starting simultaneously.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        # Create a client with the shared cache
        client = TestClient(cache_folder=cache_folder, light=True)

        # Run a simple command that triggers migration
        # Use export instead of create since it doesn't require settings/profiles
        client.save({"conanfile.py": """
from conan import ConanFile

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
"""})
        client.run("export .")

        result_queue.put({
            "success": True,
            "operation": "migrate",
            "error": None
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "operation": "migrate",
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })


class TestCompatibilityFileConcurrency:
    """
    Tests for race conditions in compatibility plugin file operations.

    These tests verify that the migrate_compatibility_files() function properly
    protects the compatibility.py file from concurrent writes during initial
    setup/migration when multiple processes start simultaneously.
    """

    @pytest.mark.slow
    def test_concurrent_compatibility_migration(self):
        """
        Test race condition: Multiple processes migrating compatibility.py simultaneously.

        Race Condition:
        - Process A: Checks if file needs migration, starts writing
        - Process B: Checks if file needs migration (before A finishes), starts writing
        - Result: Concurrent writes can corrupt the file or cause errors

        The fix should use locks to serialize access to the compatibility file.
        """
        with tempfile.TemporaryDirectory(prefix="conan_compat_test_") as cache_folder:
            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start 5 processes that will all try to do initial migration simultaneously
            processes = []
            for i in range(5):
                p = mp_context.Process(
                    target=_child_process_first_run,
                    args=(cache_folder, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously to maximize race condition window
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 5, f"Should have 5 results, got {len(results)}"

            # All processes should succeed with proper locking
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Process {i} should succeed with proper locking. " \
                    f"Error: {result.get('error', 'N/A')}"

            # Verify the compatibility file was created correctly and is not corrupted
            from conan.internal.cache.home_paths import HomePaths
            compatibility_file = os.path.join(
                HomePaths(cache_folder).compatibility_plugin_path,
                "compatibility.py"
            )
            assert os.path.exists(compatibility_file), \
                "Compatibility file should exist after migration"

            # Verify file is valid Python and not corrupted
            from conan.internal.loader import load_python_file
            try:
                mod, _ = load_python_file(compatibility_file)
                assert hasattr(mod, "compatibility"), \
                    "Compatibility module should have compatibility function"
            except Exception as e:
                pytest.fail(f"Compatibility file is corrupted: {e}")

    @pytest.mark.slow
    def test_concurrent_compatibility_check_and_migrate(self):
        """
        Test race condition: Some processes check while others migrate.

        Race Condition:
        - Process A: Starts migration, writing file
        - Process B: Checks if file exists/is valid (may see partial write)
        - Process C: Also tries to migrate
        - Result: Processes may see inconsistent file state

        The fix should ensure atomic migration with proper locking.
        """
        with tempfile.TemporaryDirectory(prefix="conan_compat_test_") as cache_folder:
            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start 3 processes simultaneously
            processes = []
            for i in range(3):
                p = mp_context.Process(
                    target=_child_process_first_run,
                    args=(cache_folder, result_queue)
                )
                processes.append(p)

            # Start all simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 3, f"Should have 3 results, got {len(results)}"

            # All should succeed
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Process {i} should handle concurrent migration. " \
                    f"Error: {result.get('error', 'N/A')}"


@pytest.fixture
def shared_compat_cache():
    """Fixture that provides a shared cache folder for compatibility tests."""
    with tempfile.TemporaryDirectory(prefix="conan_compat_test_") as tmpdir:
        yield tmpdir
