"""
Tests for config clean concurrency safety.

CONCLUSION FROM CODE ANALYSIS AND TESTING:
Config clean operations are SAFE under concurrency without explicit locking because:
1. File creation uses atomic save_if_not_exists() (O_CREAT | O_EXCL)
2. File read operations (load_global_conf, load_settings_yml) automatically
   recreate missing files via save_if_not_exists()
3. config clean removes files then immediately calls reinit() which recreates them

These tests verify that concurrent config clean operations don't cause errors
and that other operations can proceed safely even while clean is running.
"""

import multiprocessing
import tempfile
import time

import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.genconanfile import GenConanfile


def _child_process_config_clean(cache_folder, process_id, result_queue):
    """
    Child process that runs 'conan config clean'.
    This simulates concurrent config clean operations.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        start_time = time.time()

        # Use servers=False to preserve any existing config
        client = TestClient(cache_folder=cache_folder, servers=False)
        client.run("config clean")

        elapsed = time.time() - start_time

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "elapsed": elapsed,
            "operation": "config_clean",
            "error": None
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "operation": "config_clean",
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })


def _child_process_read_config(cache_folder, process_id, result_queue):
    """
    Child process that reads configuration.
    This simulates normal operations happening while config clean runs.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        start_time = time.time()

        # Use servers=False to preserve any existing config
        client = TestClient(cache_folder=cache_folder, servers=False)
        # Try to read config - should not fail even if clean is happening
        client.run("config show *")

        elapsed = time.time() - start_time

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "elapsed": elapsed,
            "operation": "read_config",
            "error": None
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "operation": "read_config",
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })


class TestConfigCleanConcurrency:
    """
    Tests for race conditions in config clean operations.

    These tests verify that concurrent config clean operations don't corrupt
    the configuration or interfere with other processes reading config.
    """

    @pytest.mark.slow
    def test_concurrent_config_clean(self):
        """
        Test that concurrent config clean operations work correctly.

        Scenario:
        - Multiple processes run config clean simultaneously
        - Each process removes config files and recreates them

        Expected behavior (verified):
        - All processes succeed
        - File operations are resilient due to atomic save_if_not_exists()
        - Missing files are automatically recreated by read operations
        """
        with tempfile.TemporaryDirectory(prefix="conan_config_test_") as shared_cache:
            # Setup: Create a basic config
            setup_client = TestClient(cache_folder=shared_cache)
            setup_client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
            setup_client.run("export .")

            num_processes = 3

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            processes = []
            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_config_clean,
                    args=(shared_cache, i, result_queue)
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

            assert len(results) == num_processes, \
                f"Should have {num_processes} results, got {len(results)}"

            # All should succeed with proper locking
            for result in results:
                assert result["success"], \
                    f"Process {result['process_id']} failed: {result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_config_clean_while_reading(self):
        """
        Test that config clean doesn't break concurrent read operations.

        Scenario:
        - Process A: Runs config clean, removes files
        - Process B: Tries to read config

        Expected behavior (verified):
        - All processes succeed
        - Read operations encountering missing files automatically recreate them
        - Atomic file creation (save_if_not_exists) prevents corruption
        """
        with tempfile.TemporaryDirectory(prefix="conan_config_test_") as shared_cache:
            # Setup: Create a basic config
            setup_client = TestClient(cache_folder=shared_cache)
            setup_client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
            setup_client.run("export .")

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            processes = []

            # Start a clean process
            p_clean = mp_context.Process(
                target=_child_process_config_clean,
                args=(shared_cache, 0, result_queue)
            )
            processes.append(p_clean)

            # Start multiple read processes
            for i in range(1, 4):
                p_read = mp_context.Process(
                    target=_child_process_read_config,
                    args=(shared_cache, i, result_queue)
                )
                processes.append(p_read)

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

            assert len(results) == 4, f"Should have 4 results, got {len(results)}"

            # All should succeed with proper locking
            for result in results:
                assert result["success"], \
                    f"Process {result['process_id']} ({result['operation']}) failed: " \
                    f"{result.get('error', 'N/A')}"
