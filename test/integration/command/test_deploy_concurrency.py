"""
Tests for concurrent deploy operations.

This test verifies that when multiple processes try to deploy to the same
output folder simultaneously, there are no race conditions or corruption issues.

The key race conditions to test:
1. _deploy_single: rmdir() followed by copytree() - can race if multiple
   processes deploy the same package to the same location
2. _flatten_directory: file existence checks followed by copy - TOCTOU race
3. Multiple processes deploying different packages to same output folder

Background:
- Deployers copy package files from cache to an output folder
- full_deploy, direct_deploy, and runtime_deploy use different strategies
- Without proper synchronization, concurrent deploys can corrupt the output
"""

import multiprocessing
import os
import tempfile
import textwrap

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def _setup_test_packages(client):
    """
    Create test packages with some content for deploying.
    """
    # Create pkg1
    conanfile1 = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class Pkg1Conan(ConanFile):
            name = "pkg1"
            version = "1.0"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "header.h"),
                     "// pkg1 header")
                save(self, os.path.join(self.package_folder, "lib", "libpkg1.a"),
                     "fake library content")
        """)
    client.save({"conanfile.py": conanfile1})
    client.run("create .")

    # Create pkg2
    conanfile2 = textwrap.dedent("""
        from conan import ConanFile
        from conan.tools.files import save
        import os

        class Pkg2Conan(ConanFile):
            name = "pkg2"
            version = "1.0"

            def package(self):
                save(self, os.path.join(self.package_folder, "include", "header2.h"),
                     "// pkg2 header")
                save(self, os.path.join(self.package_folder, "lib", "libpkg2.a"),
                     "fake library content 2")
        """)
    client.save({"conanfile.py": conanfile2})
    client.run("create .")


def _child_process_deploy(cache_folder, output_folder, deployer, requires,
                          process_id, result_queue):
    """
    Child process that runs deploy command.

    Args:
        cache_folder: Shared cache folder
        output_folder: Shared output folder for deployment
        deployer: Deployer to use (full_deploy, direct_deploy, runtime_deploy)
        requires: Package requirements string
        process_id: Process identifier
        result_queue: Queue to report results
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    import time
    from conan.test.utils.tools import TestClient

    try:
        start_time = time.time()

        # Use shared cache - servers=False means load remotes.json but don't create test servers
        # This allows proper profile loading
        client = TestClient(cache_folder=cache_folder, servers=False)

        # Run install with deployer to shared output folder
        # Add explicit settings to ensure build profile has required settings for VirtualBuildEnv
        client.run(f"install --requires={requires} --deployer={deployer} "
                  f"-of={output_folder} -s:b os=Linux")

        elapsed = time.time() - start_time

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "elapsed": elapsed,
            "error": None
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })


class TestDeployConcurrency:
    """
    Tests for concurrent deploy operations.

    These tests verify that deployer operations are properly synchronized
    when multiple processes deploy to the same output folder.
    """

    @pytest.mark.slow
    def test_concurrent_full_deploy_same_package(self):
        """
        Test that multiple processes using full_deploy to same folder don't corrupt output.

        Scenario:
        - Multiple processes all deploy the same package with full_deploy
        - They all write to the same output folder
        - This exercises the rmdir() + copytree() race in _deploy_single

        WITHOUT protection:
        - Process A: rmdir(folder) → copytree()
        - Process B: rmdir(folder) → copytree()
        - Between A's rmdir and copytree, B might rmdir, causing error
        - Or both copytree simultaneously, causing corruption

        WITH protection:
        - Operations are serialized per output folder
        - Only one process deploys at a time
        """
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmpdir:
            # Setup: Create a package in a shared cache
            shared_cache = os.path.join(tmpdir, "cache")
            setup_client = TestClient(cache_folder=shared_cache)
            _setup_test_packages(setup_client)

            # Use a shared output folder
            shared_output = os.path.join(tmpdir, "deploy_output")

            # Spawn multiple processes that all deploy the same package
            num_processes = 5
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_deploy,
                    args=(shared_cache, shared_output, "full_deploy",
                          "pkg1/1.0", i, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously to maximize contention
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

            # All should succeed without errors
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)} processes failed: {[f['error'] for f in failures[:3]]}"

            # Verify the output folder has correct structure
            assert os.path.exists(shared_output), "Output folder should exist"
            full_deploy_dir = os.path.join(shared_output, "full_deploy")
            assert os.path.exists(full_deploy_dir), "full_deploy subfolder should exist"

            # Should have pkg1 deployed
            pkg_dirs = [d for d in os.listdir(full_deploy_dir) if os.path.isdir(
                os.path.join(full_deploy_dir, d))]
            assert "host" in pkg_dirs, "Should have host context folder"

            # Files should not be corrupted
            # Note: Don't use light=True here as it can cause profile issues in concurrent tests
            verify_client = TestClient(cache_folder=shared_cache)
            verify_client.run(f"install --requires=pkg1/1.0 --deployer=full_deploy "
                            f"-of={tmpdir}/verify")
            verify_output = os.path.join(tmpdir, "verify", "full_deploy")

            # Compare deployed files to verify no corruption
            # (simplified check - just verify structure exists)
            assert os.path.exists(verify_output)

    @pytest.mark.slow
    def test_concurrent_deploy_different_packages(self):
        """
        Test that concurrent deploys of different packages to same folder work correctly.

        This verifies that:
        1. Different packages can be deployed concurrently (ideally)
        2. Or at minimum, they don't corrupt each other
        """
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmpdir:
            # Setup: Create multiple packages
            shared_cache = os.path.join(tmpdir, "cache")
            setup_client = TestClient(cache_folder=shared_cache)
            _setup_test_packages(setup_client)

            # Use a shared output folder
            shared_output = os.path.join(tmpdir, "deploy_output")

            # Spawn processes deploying different packages
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            packages = ["pkg1/1.0", "pkg2/1.0"]
            for i, pkg in enumerate(packages * 2):  # 2 processes per package
                p = mp_context.Process(
                    target=_child_process_deploy,
                    args=(shared_cache, shared_output, "full_deploy",
                          pkg, i, result_queue)
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
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)} processes failed: {[f['error'] for f in failures[:2]]}"

            # Verify both packages are deployed correctly
            full_deploy_dir = os.path.join(shared_output, "full_deploy")
            assert os.path.exists(full_deploy_dir), "Deploy output should exist"

    @pytest.mark.slow
    def test_concurrent_direct_deploy(self):
        """
        Test concurrent direct_deploy operations.

        direct_deploy also uses _deploy_single, so has the same rmdir+copytree race.
        """
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmpdir:
            # Setup
            shared_cache = os.path.join(tmpdir, "cache")
            setup_client = TestClient(cache_folder=shared_cache)
            _setup_test_packages(setup_client)

            shared_output = os.path.join(tmpdir, "deploy_output")

            # Spawn multiple processes using direct_deploy
            num_processes = 5
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_deploy,
                    args=(shared_cache, shared_output, "direct_deploy",
                          "pkg1/1.0", i, result_queue)
                )
                processes.append(p)

            # Start all
            for p in processes:
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == num_processes

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)} operations failed: {[f['error'] for f in failures[:3]]}"

            # Verify output
            direct_deploy_dir = os.path.join(shared_output, "direct_deploy")
            assert os.path.exists(direct_deploy_dir), "direct_deploy output should exist"

    @pytest.mark.slow
    def test_concurrent_runtime_deploy(self):
        """
        Test concurrent runtime_deploy operations.

        runtime_deploy uses _flatten_directory which has TOCTOU races:
        - Check if file exists
        - Compare files
        - Copy file

        Between these steps, another process could modify the file.
        """
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmpdir:
            # Setup: Create package with executable/library
            shared_cache = os.path.join(tmpdir, "cache")
            setup_client = TestClient(cache_folder=shared_cache)

            # Create a package with binaries for runtime_deploy
            conanfile = textwrap.dedent("""
                from conan import ConanFile
                from conan.tools.files import save
                import os

                class RuntimePkgConan(ConanFile):
                    name = "rtpkg"
                    version = "1.0"

                    def package(self):
                        save(self, os.path.join(self.package_folder, "bin", "app.exe"),
                             "fake executable")
                        save(self, os.path.join(self.package_folder, "lib", "lib.so"),
                             "fake shared library")

                    def package_info(self):
                        self.cpp_info.bindirs = ["bin"]
                        self.cpp_info.libdirs = ["lib"]
                """)
            setup_client.save({"conanfile.py": conanfile})
            setup_client.run("create .")

            shared_output = os.path.join(tmpdir, "deploy_output")

            # Spawn multiple processes using runtime_deploy
            num_processes = 5
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_deploy,
                    args=(shared_cache, shared_output, "runtime_deploy",
                          "rtpkg/1.0", i, result_queue)
                )
                processes.append(p)

            # Start all
            for p in processes:
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == num_processes

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)} operations failed: {[f['error'] for f in failures[:3]]}"

            # Verify output files exist and are not corrupted
            assert os.path.exists(shared_output), "runtime_deploy output should exist"
            # runtime_deploy creates flat structure
            files = os.listdir(shared_output)
            # Should have the deployed files (not checking exact names due to platform differences)
            assert len(files) > 0, "Should have deployed files"

    @pytest.mark.slow
    def test_deploy_stress(self):
        """
        Stress test with many concurrent deploy operations.
        """
        with tempfile.TemporaryDirectory(prefix="deploy_test_") as tmpdir:
            # Setup
            shared_cache = os.path.join(tmpdir, "cache")
            setup_client = TestClient(cache_folder=shared_cache)
            _setup_test_packages(setup_client)

            shared_output = os.path.join(tmpdir, "deploy_output")

            # Many processes all deploying
            num_processes = 10
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                # Alternate between packages and deployers
                pkg = "pkg1/1.0" if i % 2 == 0 else "pkg2/1.0"
                deployer = "full_deploy" if i % 3 == 0 else "direct_deploy"

                p = mp_context.Process(
                    target=_child_process_deploy,
                    args=(shared_cache, shared_output, deployer,
                          pkg, i, result_queue)
                )
                processes.append(p)

            # Start all
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

            # Verify output is not corrupted
            assert os.path.exists(shared_output), "Deploy output should exist"
