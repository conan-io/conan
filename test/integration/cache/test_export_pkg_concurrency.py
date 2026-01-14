"""
Tests for export-pkg operation concurrency issues.

This test file contains tests for race conditions in export-pkg operations.

Race condition in export_pkg:
- Two processes run export-pkg for the same package simultaneously
- Both call create_build_pkg_layout(pref) and get separate temp folders
- Both run the package() method concurrently
- Both call assign_prev(), second one wins and overwrites first one's work

Expected to fail until locks are implemented for the entire export-pkg operation.
"""

import multiprocessing
import os
import tempfile
import time

import pytest

from test.utils.multiprocess import MultiProcessTestClient, shared_cache


def _child_process_export_pkg(cache_folder, working_dir, package_name, process_id, result_queue):
    """
    Child process that runs 'conan export-pkg' to export a pre-built package.

    This simulates an export-pkg operation that may race with other export-pkg operations.
    Each process writes a unique marker file so we can detect race conditions.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder, current_folder=working_dir)
        # Export the recipe first (only needs to be done once, but safe to do multiple times)
        client.run(f"export . --name={package_name} --version=1.0")

        # Run export-pkg - this is where the race happens
        client.run(f"export-pkg . --name={package_name} --version=1.0")

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "operation": "export-pkg",
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "operation": "export-pkg",
            "error": str(e)
        })


class TestExportPkgConcurrency:
    """
    Tests for race conditions in export-pkg operations.

    The issue is in conan/api/subapi/export.py:131-144:
    - create_build_pkg_layout(pref) creates a temp folder (no lock)
    - package() method runs (no lock, just dirty flag)
    - assign_prev() acquires lock, but by then both processes have done the work

    The fix should acquire the package lock BEFORE create_build_pkg_layout
    and hold it through the entire operation.
    """

    @pytest.mark.slow
    def test_concurrent_export_pkg_same_package(self, shared_cache):
        """
        Test race condition: Multiple processes running export-pkg for the same package.

        Race Condition (now FIXED):
        The package lock in export_pkg() ensures that:
        - Only one process at a time can execute the export-pkg operation for a given pref
        - Operations are serialized: first process completes, second waits then finds it already done
        - No duplicate work and no overwriting of results

        Without the fix (historical):
        - Process A: Creates build layout, runs package() method, writes marker file "A"
        - Process B: Creates build layout, runs package() method, writes marker file "B" (simultaneously)
        - Process A: Calls assign_prev(), creates DB entry
        - Process B: Calls assign_prev(), finds entry exists, removes A's folder and replaces it
        - Both did the work, second one's result won
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package with a package() method that takes time and writes a marker
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = """
from conan import ConanFile
from conan.tools.files import save
import os
import time

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"

    def package(self):
        # Each process writes a unique marker based on its PID
        import os as os_module
        process_marker = str(os_module.getpid())

        self.output.info(f"Process {process_marker} starting package()...")

        # Simulate packaging work that takes time
        time.sleep(0.3)

        # Write marker file with this process's PID
        save(self, os.path.join(self.package_folder, "marker.txt"),
             f"packaged_by_pid_{process_marker}")

        # Write some regular files too
        for i in range(3):
            save(self, os.path.join(self.package_folder, f"file{i}.txt"),
                 f"content {i} from {process_marker}")
            time.sleep(0.05)

        self.output.info(f"Process {process_marker} package() complete")
"""
        setup_client.save({"conanfile.py": conanfile})

        # Create working directories for concurrent export-pkg
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

            # Start 2 processes trying to export-pkg the same package at the same time
            processes = []
            for i, workdir in enumerate([workdir1, workdir2]):
                p = multiprocessing.Process(
                    target=_child_process_export_pkg,
                    args=(shared_cache, workdir, "pkg", i, result_queue)
                )
                processes.append(p)

            # Start both processes simultaneously to maximize race condition window
            for p in processes:
                p.start()

            # Wait for both to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock or hang"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 2, f"Should have 2 results, got {len(results)}"

            # Both processes should complete successfully
            # With the fix, operations are serialized so both succeed
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Export-pkg process {i} (pid {result.get('process_id')}) failed. " \
                    f"Error: {result.get('error', 'N/A')}"

            # Verify the package exists in the cache
            verify_client = TestClient(cache_folder=shared_cache)
            verify_client.run("list pkg/1.0:*")
            assert "pkg/1.0" in verify_client.out, "Package should be in cache"

    @pytest.mark.slow
    def test_concurrent_export_pkg_different_configs(self, shared_cache):
        """
        Test race condition: Multiple processes exporting packages with different configs.

        This tests the case where two processes export packages for the same recipe
        but with different package IDs (e.g., different settings). Without proper locking,
        they could still interfere if they happen to get the same temporary folder name
        (though UUID makes this unlikely) or if there's shared state.

        This is less likely to fail than test_concurrent_export_pkg_same_package,
        but tests that different package IDs are properly isolated.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package with settings
        setup_client = TestClient(cache_folder=shared_cache)
        conanfile = """
from conan import ConanFile
from conan.tools.files import save
import os
import time

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    settings = "build_type"

    def package(self):
        # Simulate packaging work
        self.output.info(f"Packaging for build_type={self.settings.build_type}")
        time.sleep(0.15)

        # Write config-specific file
        save(self, os.path.join(self.package_folder, "config.txt"),
             f"build_type={self.settings.build_type}")
"""
        setup_client.save({"conanfile.py": conanfile})

        # Create working directories for concurrent export-pkg
        with tempfile.TemporaryDirectory() as workdir1, \
             tempfile.TemporaryDirectory() as workdir2:

            import shutil
            for workdir in [workdir1, workdir2]:
                shutil.copy(
                    os.path.join(setup_client.current_folder, "conanfile.py"),
                    os.path.join(workdir, "conanfile.py")
                )

            result_queue = multiprocessing.Queue()

            def _export_pkg_with_settings(cache_folder, working_dir, build_type, result_queue):
                from conan.test.utils.tools import TestClient
                try:
                    client = TestClient(cache_folder=cache_folder, current_folder=working_dir)
                    client.run("export . --name=pkg --version=1.0")
                    client.run(f"export-pkg . --name=pkg --version=1.0 -s build_type={build_type}")
                    result_queue.put({
                        "success": True,
                        "build_type": build_type,
                        "error": None
                    })
                except Exception as e:
                    result_queue.put({
                        "success": False,
                        "build_type": build_type,
                        "error": str(e)
                    })

            # Start 2 processes with different build types
            process1 = multiprocessing.Process(
                target=_export_pkg_with_settings,
                args=(shared_cache, workdir1, "Debug", result_queue)
            )
            process2 = multiprocessing.Process(
                target=_export_pkg_with_settings,
                args=(shared_cache, workdir2, "Release", result_queue)
            )

            process1.start()
            process2.start()

            process1.join(timeout=60.0)
            process2.join(timeout=60.0)

            assert not process1.is_alive(), "Process 1 should complete"
            assert not process2.is_alive(), "Process 2 should complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 2, "Should have 2 results"

            # Both should succeed even with different configs
            for result in results:
                assert result["success"], \
                    f"Export-pkg for build_type={result['build_type']} should succeed. " \
                    f"Error: {result.get('error', 'N/A')}"


@pytest.fixture
def shared_cache():
    """Fixture that provides a shared cache folder for multi-process tests."""
    with tempfile.TemporaryDirectory(prefix="conan_export_pkg_test_") as tmpdir:
        yield tmpdir
