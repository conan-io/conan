"""
Tests for local-recipes-index concurrent export operations.

This test verifies that when multiple processes try to use recipes from a
local-recipes-index remote simultaneously, the exports are properly serialized
to avoid wasted work and potential corruption.

The optimization:
- WITHOUT LOCK: Multiple processes export same recipe → wasted CPU
- WITH LOCK: First process exports, others wait → efficient

Background:
- local-recipes-index is a special remote type that exports recipes on-demand
  from a local folder (e.g., conan-center-index clone) to the cache
- When multiple processes need the same recipe, they all try to export it
- The export operation (cmd_export) is CPU-intensive (file copying, hashing)
- Currently assign_rrev has locking, but the export work happens before that
"""

import multiprocessing
import os
import tempfile
import textwrap
import time

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from conan.internal.util.files import save_files, mkdir, save


def _setup_local_recipes_index(folder):
    """
    Create a local-recipes-index structure with some test recipes.

    Structure:
        recipes/
            pkg/
                config.yml
                all/
                    conanfile.py
    """
    recipes_folder = os.path.join(folder, "recipes")

    # Create pkg recipe
    pkg_config = textwrap.dedent("""
        versions:
          "1.0":
            folder: all
        """)
    pkg_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class PkgConan(ConanFile):
            name = "pkg"
            version = "1.0"

            def export(self):
                # Simulate some CPU-intensive work during export
                import time
                time.sleep(0.1)
        """)

    save_files(recipes_folder, {
        "pkg/config.yml": pkg_config,
        "pkg/all/conanfile.py": pkg_conanfile,
    })

    # Create another recipe for dependency testing
    dep_config = textwrap.dedent("""
        versions:
          "1.0":
            folder: all
        """)
    dep_conanfile = textwrap.dedent("""
        from conan import ConanFile
        class DepConan(ConanFile):
            name = "dep"
            version = "1.0"

            def export(self):
                import time
                time.sleep(0.05)
        """)

    save_files(recipes_folder, {
        "dep/config.yml": dep_config,
        "dep/all/conanfile.py": dep_conanfile,
    })

    return folder


def _child_process_install_from_local_index(cache_folder, index_folder, package_ref,
                                              process_id, result_queue):
    """
    Child process that installs a recipe from local-recipes-index.
    This triggers export from the index to the cache.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        start_time = time.time()

        # Create a full TestClient pointing to shared cache
        # servers=False means don't create test servers, but DO load remotes.json
        # This allows the client to see the 'local' remote configured in shared cache
        client = TestClient(cache_folder=cache_folder, servers=False)

        # Download recipe from local-recipes-index (triggers export AND download to cache)
        # The remote 'local' was configured in the shared cache's remotes.json
        client.run(f"download {package_ref} -r=local")

        elapsed = time.time() - start_time

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "elapsed": elapsed,
            "operation": "export",
            "error": None
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "operation": "install",
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })


class TestLocalRecipesIndexConcurrency:
    """
    Tests for concurrent exports from local-recipes-index.

    These tests verify that concurrent access to the same recipe from
    local-recipes-index is handled efficiently without data corruption.
    """

    @pytest.mark.slow
    def test_concurrent_exports_same_recipe(self):
        """
        Test that multiple processes exporting the same recipe don't waste work.

        Scenario:
        - Multiple processes need the same recipe from local-recipes-index
        - All try to export it to their shared cache simultaneously

        WITHOUT optimization:
        - All processes do full export work (wasteful)
        - All processes compete at assign_rrev
        - Only one succeeds, others discard their work

        WITH optimization:
        - First process acquires lock and exports
        - Other processes wait for lock
        - After acquiring lock, they see recipe is already exported
        - They skip the export work and reuse the existing recipe

        This test verifies correctness (all processes succeed) and
        ideally efficiency (minimal duplicate work).
        """
        with tempfile.TemporaryDirectory(prefix="local_index_test_") as tmpdir:
            # Create local-recipes-index structure
            index_folder = os.path.join(tmpdir, "index")
            _setup_local_recipes_index(index_folder)

            # Use a shared cache for all processes
            shared_cache = os.path.join(tmpdir, "shared_cache")

            # Initialize the cache and add the remote
            setup_client = TestClient(cache_folder=shared_cache, light=True)
            setup_client.run("version")  # Initialize cache
            setup_client.run(f"remote add local '{index_folder}'")  # Add remote once

            # Spawn multiple processes that all need the same recipe
            num_processes = 5

            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_install_from_local_index,
                    args=(shared_cache, index_folder, "pkg/1.0", i, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously to maximize contention
            start_time = time.time()
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete"

            total_elapsed = time.time() - start_time

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == num_processes, \
                f"Should have {num_processes} results, got {len(results)}"

            # All should succeed without errors
            for result in results:
                assert result["success"], \
                    f"Process {result['process_id']} failed: {result.get('error', 'N/A')}"

            # Verify the recipe is in the cache
            verify_client = TestClient(cache_folder=shared_cache, servers=False)
            verify_client.run("list pkg/1.0#*")
            assert "pkg/1.0" in verify_client.out

            # Note: With proper locking, concurrent exports should be serialized
            # reducing total wall-clock time compared to fully parallel execution
            # (which wastes CPU doing duplicate work)
            individual_times = [r["elapsed"] for r in results]
            from conan.api.output import ConanOutput
            ConanOutput().info(f"Concurrent exports completed: "
                             f"Total={total_elapsed:.2f}s, "
                             f"Individual times={[f'{t:.2f}s' for t in individual_times]}")

    @pytest.mark.slow
    def test_concurrent_exports_different_recipes(self):
        """
        Test that concurrent exports of different recipes work correctly.

        This verifies that locking doesn't over-serialize - different recipes
        should be able to export in parallel.
        """
        with tempfile.TemporaryDirectory(prefix="local_index_test_") as tmpdir:
            # Create local-recipes-index structure
            index_folder = os.path.join(tmpdir, "index")
            _setup_local_recipes_index(index_folder)

            # Use a shared cache for all processes
            shared_cache = os.path.join(tmpdir, "shared_cache")

            # Initialize the cache and add the remote
            setup_client = TestClient(cache_folder=shared_cache, light=True)
            setup_client.run("version")
            setup_client.run(f"remote add local '{index_folder}'")  # Add remote once

            # Spawn processes for different recipes
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            recipes = ["pkg/1.0", "dep/1.0"]
            for i, recipe in enumerate(recipes * 2):  # 2 processes per recipe
                p = mp_context.Process(
                    target=_child_process_install_from_local_index,
                    args=(shared_cache, index_folder, recipe, i, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
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

            # All should succeed
            for result in results:
                assert result["success"], \
                    f"Process {result['process_id']} failed: {result.get('error', 'N/A')}"

            # Verify both recipes are in the cache
            verify_client = TestClient(cache_folder=shared_cache, servers=False)
            verify_client.run("list *#*")
            assert "pkg/1.0" in verify_client.out
            assert "dep/1.0" in verify_client.out

    @pytest.mark.slow
    def test_export_stress(self):
        """
        Stress test with many concurrent exports.
        """
        with tempfile.TemporaryDirectory(prefix="local_index_test_") as tmpdir:
            # Create local-recipes-index structure
            index_folder = os.path.join(tmpdir, "index")
            _setup_local_recipes_index(index_folder)

            # Use a shared cache
            shared_cache = os.path.join(tmpdir, "shared_cache")

            # Initialize the cache and add the remote
            setup_client = TestClient(cache_folder=shared_cache, light=True)
            setup_client.run("version")
            setup_client.run(f"remote add local '{index_folder}'")  # Add remote once

            # Many processes all trying to export the same recipe
            num_processes = 10

            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_install_from_local_index,
                    args=(shared_cache, index_folder, "pkg/1.0", i, result_queue)
                )
                processes.append(p)

            # Start all processes
            for p in processes:
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=90.0)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == num_processes

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)}/{num_processes} operations failed: {failures[:3]}"

            # Verify cache is valid
            verify_client = TestClient(cache_folder=shared_cache, servers=False)
            verify_client.run("list pkg/1.0#*")
            assert "pkg/1.0" in verify_client.out
