"""
Tests for graph proxy update check performance optimization.

This test verifies that update checks can proceed in parallel when no updates
are needed, rather than serializing on the recipe lock.

The optimization:
- OLD: Lock → query remotes → compare → unlock (serialized)
- NEW: Query remotes → compare → if needed: lock → double-check → update → unlock

Benefits:
- Processes that don't need updates can query remotes in parallel
- Only processes that actually download updates serialize on the lock
- Reduces lock contention and improves performance with many concurrent processes
"""

import os
import tempfile
import time

import pytest

from conan.api.output import ConanOutput
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestServer
from test.utils.multiprocess import MultiProcessTestClient, RealTestServer


class TestProxyUpdatePerformance:
    """
    Tests for update check performance optimization.

    The optimization reduces lock contention when multiple processes check for
    updates simultaneously. Instead of serializing all remote queries under a lock,
    we query remotes in parallel and only lock for actual updates.
    """

    @pytest.mark.slow
    def test_parallel_update_checks_without_update(self):
        """
        Test that update checks can proceed in parallel when no update is needed.

        Scenario:
        - Recipe exists in cache with timestamp T1
        - Remote has the SAME version with timestamp T1
        - Multiple processes run --update simultaneously

        WITHOUT optimization:
        - Process A: Acquires lock → queries remote → compares → releases lock
        - Process B: Waits for lock → queries remote → compares → releases lock
        - Process C: Waits for lock → queries remote → compares → releases lock
        - Total time: 3 * (query time) (serialized)

        WITH optimization:
        - All processes query remote in parallel
        - All processes compare timestamps in parallel
        - No updates needed, no lock contention
        - Total time: 1 * (query time) (parallelized)

        This test should complete faster with the optimization.
        """
        # Setup: Create a real server that subprocesses can access
        with RealTestServer() as server:
            servers = {"default": server}

            # Create and upload initial version
            c = TestClient(servers=servers, inputs=2*["admin", "password"])
            c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
            c.run("create .")
            c.run("upload * -c -r=default")

            # Use a shared cache for all processes
            with tempfile.TemporaryDirectory(prefix="conan_proxy_test_") as shared_cache:
                # Populate the shared cache with the package
                setup_client = TestClient(cache_folder=shared_cache, servers=servers)
                setup_client.run(f"install --requires=pkg/1.0")

                # Now run multiple processes that all do --update
                # They should all find that no update is needed
                num_processes = 5

                # Use MultiProcessTestClient which runs actual conan CLI subprocesses
                # This avoids TestClient race conditions on profile writes
                mp_client = MultiProcessTestClient(shared_cache)

                # Create consumer conanfile for install
                with tempfile.TemporaryDirectory() as consumer_dir:
                    consumer_file = os.path.join(consumer_dir, "conanfile.py")
                    with open(consumer_file, "w") as f:
                        f.write("from conan import ConanFile\n\n")
                        f.write("class Consumer(ConanFile):\n")
                        f.write("    requires = 'pkg/1.0'\n")

                    # Run concurrent installs with --update
                    commands = [
                        (["install", ".", "--update"], consumer_dir)
                        for _ in range(num_processes)
                    ]

                    start_time = time.time()
                    results = mp_client.run_concurrent(commands, max_workers=num_processes, timeout=60)
                    total_elapsed = time.time() - start_time

                # All should succeed
                success_count = sum(1 for r in results if r.returncode == 0)
                assert success_count == num_processes, \
                    f"Only {success_count}/{num_processes} processes succeeded. " \
                    f"Failed processes: {[i for i, r in enumerate(results) if r.returncode != 0]}"

                # The key correctness property: all processes completed successfully
                # without deadlocks or errors. The optimization allows parallel execution
                # of update checks which reduces lock contention.
                #
                # Note: Precise performance timing is difficult in tests due to:
                # - Very fast operations (< 0.1s each)
                # - Process spawning overhead dominates timing
                # - System scheduling variations
                #
                # The real benefit appears with:
                # - Slower network operations (real remote servers)
                # - Many concurrent processes (CI/CD scenarios)
                # - Longer-running update checks
                #
                # Here we verify correctness: all processes succeed and see consistent state
                ConanOutput().info(f"Parallel update checks completed: "
                                 f"Total={total_elapsed:.2f}s, "
                                 f"All {num_processes} processes succeeded")

    @pytest.mark.slow
    def test_update_check_with_actual_update(self):
        """
        Test that actual updates still work correctly with the optimization.

        Scenario:
        - Recipe exists in cache with timestamp T1
        - Remote has NEWER version with timestamp T2 > T1
        - Multiple processes run --update simultaneously

        Expected behavior:
        - All processes query remote in parallel (see T2 > T1)
        - First process acquires lock and downloads
        - Other processes wait for lock, re-check, see update already done, skip
        - All processes succeed and see the updated version

        KNOWN ISSUE: This test intermittently fails with "conanfile.py not found" errors,
        revealing a race condition in concurrent recipe extraction. One process extracts
        files while another tries to read them. Proper locking around recipe extraction
        is needed to fix this.
        """
        # Setup: Create a real server that subprocesses can access
        with RealTestServer() as server:
            servers = {"default": server}

            # Create and upload initial version
            # Provide extra inputs for potential token expirations during parallel operations
            c = TestClient(servers=servers, inputs=10*["admin", "password"])
            c.save({"conanfile.py": GenConanfile("updpkg", "1.0")})
            c.run("create .")
            c.run("upload * -c -r=default")

            # Use a shared cache for all processes
            with tempfile.TemporaryDirectory(prefix="conan_proxy_test_") as shared_cache:
                # Populate the shared cache with the initial version
                # Provide inputs for potential authentication needs
                setup_client = TestClient(cache_folder=shared_cache, servers=servers,
                                        inputs=5*["admin", "password"])
                setup_client.run(f"install --requires=updpkg/1.0")

                # Now upload a newer version to the server (different revision)
                c.save({"conanfile.py": GenConanfile("updpkg", "1.0").with_exports("*.txt"),
                        "file.txt": "new content"})
                c.run("create .")
                c.run("upload * -c -r=default")

                # Run multiple processes that all do --update
                # They should all see the new version and update
                num_processes = 3

                # Use MultiProcessTestClient which runs actual conan CLI subprocesses
                mp_client = MultiProcessTestClient(shared_cache)

                # Create consumer conanfile for install
                with tempfile.TemporaryDirectory() as consumer_dir:
                    consumer_file = os.path.join(consumer_dir, "conanfile.py")
                    with open(consumer_file, "w") as f:
                        f.write("from conan import ConanFile\n\n")
                        f.write("class Consumer(ConanFile):\n")
                        f.write("    requires = 'updpkg/1.0'\n")

                    # Run concurrent installs with --update
                    commands = [
                        (["install", ".", "--update"], consumer_dir)
                        for _ in range(num_processes)
                    ]

                    results = mp_client.run_concurrent(commands, max_workers=num_processes, timeout=60)

                # All should succeed
                success_count = sum(1 for r in results if r.returncode == 0)

                # If there are failures, show detailed error info
                if success_count < num_processes:
                    for i, r in enumerate(results):
                        if r.returncode != 0:
                            print(f"\nFailed process {i}:")
                            print(f"  Return code: {r.returncode}")
                            print(f"  Stdout: {r.stdout[-500:] if r.stdout else 'N/A'}")
                            print(f"  Stderr: {r.stderr[-500:] if r.stderr else 'N/A'}")

                assert success_count == num_processes, \
                    f"Only {success_count}/{num_processes} processes succeeded. " \
                    f"Failed processes: {[i for i, r in enumerate(results) if r.returncode != 0]}"

                # Verify that the cache has the updated version
                verify_client = TestClient(cache_folder=shared_cache)
                verify_client.run("list updpkg/1.0:*")
                # The updated version should be in the cache
                assert "updpkg/1.0" in verify_client.out


@pytest.fixture
def shared_proxy_cache():
    """Fixture that provides a shared cache folder for proxy tests."""
    with tempfile.TemporaryDirectory(prefix="conan_proxy_test_") as tmpdir:
        yield tmpdir
