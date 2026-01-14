"""
Tests for build and source operation concurrency issues.

This test file contains tests for race conditions in build and source operations
that are currently marked as TODO in the codebase (installer.py:129-137).

Expected to fail until locks are implemented for:
- Source folder copying operations
- Build folder operations
- set_dirty/clean_dirty calls
"""

import multiprocessing
import os
import tempfile
import time

import pytest

from test.utils.multiprocess import MultiProcessTestClient, shared_cache


def _child_process_build_package(cache_folder, working_dir, package_name, result_queue):
    """
    Child process that runs 'conan create' to build a package.

    This simulates a build operation that may race with other builds.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder, current_folder=working_dir)
        client.run(f"create . --name={package_name} --version=1.0")

        result_queue.put({
            "success": True,
            "operation": "build",
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "build",
            "error": str(e)
        })


def _child_process_install_package(cache_folder, package_ref, result_queue):
    """
    Child process that runs 'conan install' to trigger build from cache.

    This may race with concurrent create operations.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        client = TestClient(cache_folder=cache_folder)
        client.run(f"install --requires={package_ref} --build=missing")

        result_queue.put({
            "success": True,
            "operation": "install",
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "install",
            "error": str(e)
        })


class TestBuildSourceConcurrency:
    """
    Tests for race conditions in build and source operations.

    These tests verify that package_lock properly protects:
    - Source copying to build folder
    - set_dirty/clean_dirty operations
    - Build operations in the build folder
    - Package operations

    Previously, these operations had TODOs at installer.py:129-137.
    The fix implements package_lock around the entire build_package operation.
    """

    @pytest.mark.slow
    def test_concurrent_build_same_package(self, shared_cache):
        """
        Test race condition: Multiple processes building the same package simultaneously.

        Race Condition (now prevented):
        - Process A: Copies sources to build folder, starts build
        - Process B: Copies sources to build folder at the same time
        - With locking: Operations are serialized, both succeed

        The package_lock ensures that only one process builds a package at a time.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package with sources that need copying
        setup_client = TestClient(cache_folder=shared_cache)
        # Ensure profiles are created before spawning child processes
        setup_client.run("profile detect", assert_error=True)
        conanfile = """
from conan import ConanFile
from conan.tools.files import save, load, copy
import os

class Pkg(ConanFile):
    name = "pkg"
    version = "1.0"
    exports_sources = "*.txt"

    def build(self):
        # Simulate build that reads source files
        # This increases the window for race conditions
        source_file = os.path.join(self.source_folder, "data.txt")
        if os.path.exists(source_file):
            content = load(self, source_file)
            self.output.info(f"Building with source: {content}")

        # Slow build to widen race window
        import time
        time.sleep(0.1)

        # Write build output
        save(self, os.path.join(self.build_folder, "output.txt"), "built")

    def package(self):
        copy(self, "*.txt", src=self.build_folder, dst=self.package_folder)
"""
        setup_client.save({
            "conanfile.py": conanfile,
            "data.txt": "source data"
        })

        # Export the recipe first so both processes use the same recipe
        setup_client.run("export .")

        # Create working directories for concurrent builds
        with tempfile.TemporaryDirectory() as workdir1, \
             tempfile.TemporaryDirectory() as workdir2:

            # Copy conanfile and sources to both working dirs
            import shutil
            for workdir in [workdir1, workdir2]:
                shutil.copy(
                    os.path.join(setup_client.current_folder, "conanfile.py"),
                    os.path.join(workdir, "conanfile.py")
                )
                shutil.copy(
                    os.path.join(setup_client.current_folder, "data.txt"),
                    os.path.join(workdir, "data.txt")
                )

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start 2 processes trying to build the same package at the same time
            processes = []
            for i, workdir in enumerate([workdir1, workdir2]):
                p = mp_context.Process(
                    target=_child_process_build_package,
                    args=(shared_cache, workdir, "pkg", result_queue)
                )
                processes.append(p)

            # Start both processes simultaneously to maximize race condition
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

            assert len(results) == 2, "Should have 2 results"

            # EXPECTED (with proper locking): Both builds succeed, operations serialized
            # CURRENT (without locking): May fail with corrupted sources or build errors
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Build process {i} should succeed with proper locking. " \
                    f"Error: {result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_concurrent_build_and_install(self, shared_cache):
        """
        Test race condition: Building a package while another process installs it.

        Race Condition (now prevented):
        - Process A: Running 'conan create' (building package from source)
        - Process B: Running 'conan install --build=missing' (may trigger build)
        - With locking: One process waits, builds are serialized

        The package_lock ensures that concurrent build attempts are safely serialized.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package with a noticeable build step
        setup_client = TestClient(cache_folder=shared_cache)
        # Ensure profiles are created before spawning child processes
        setup_client.run("profile detect", assert_error=True)
        conanfile = """
from conan import ConanFile
from conan.tools.files import save, copy
import os
import time

class Pkg(ConanFile):
    name = "buildpkg"
    version = "1.0"
    settings = "os", "compiler", "build_type", "arch"

    def build(self):
        self.output.info("Starting build...")
        # Slow build to increase race window
        time.sleep(0.2)

        # Write marker file
        save(self, os.path.join(self.build_folder, "marker.txt"), "built")

        self.output.info("Build complete")

    def package(self):
        copy(self, "*.txt", src=self.build_folder, dst=self.package_folder)
"""
        setup_client.save({"conanfile.py": conanfile})

        # Export the recipe so install can find it
        setup_client.run("export .")

        # Create working directory for create process
        with tempfile.TemporaryDirectory() as workdir:
            import shutil
            shutil.copy(
                os.path.join(setup_client.current_folder, "conanfile.py"),
                os.path.join(workdir, "conanfile.py")
            )

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Process A: Create the package (build from source)
            process_create = mp_context.Process(
                target=_child_process_build_package,
                args=(shared_cache, workdir, "buildpkg", result_queue)
            )

            # Process B: Install with --build=missing (may trigger build)
            process_install = mp_context.Process(
                target=_child_process_install_package,
                args=(shared_cache, "buildpkg/1.0", result_queue)
            )

            # Start create first
            process_create.start()
            # Wait a tiny bit, then start install
            time.sleep(0.05)
            process_install.start()

            # Wait for both to complete
            process_create.join(timeout=60.0)
            process_install.join(timeout=60.0)

            assert not process_create.is_alive(), "Create process should complete"
            assert not process_install.is_alive(), "Install process should complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 2, "Should have 2 results"

            # EXPECTED (with proper locking): Both succeed, one waits for the other
            # CURRENT (without locking): May fail with concurrent build corruption
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Process {i} ({result['operation']}) should succeed with proper locking. " \
                    f"Error: {result.get('error', 'N/A')}"

    @pytest.mark.slow
    def test_concurrent_source_folder_access(self, shared_cache):
        """
        Test race condition: Multiple builds reading from the same source folder.

        Race Condition (now prevented):
        - Process A: Running source() method, populating source folder
        - Process B: Trying to read from source folder for its build
        - With locking: Source operations are protected by source_lock,
          and build operations are protected by package_lock

        The combination of source_lock (for source() method) and package_lock
        (for build operations) ensures safe concurrent access.
        """
        from conan.test.utils.tools import TestClient

        # Setup: Create a package with a source() method that takes time
        setup_client = TestClient(cache_folder=shared_cache)
        # Ensure profiles are created before spawning child processes
        setup_client.run("profile detect", assert_error=True)
        conanfile = """
from conan import ConanFile
from conan.tools.files import save, load
import os
import time

class Pkg(ConanFile):
    name = "srcpkg"
    version = "1.0"

    def source(self):
        # Simulate slow source fetch (e.g., git clone)
        self.output.info("Fetching sources...")
        time.sleep(0.15)

        # Create multiple source files
        for i in range(5):
            save(self, os.path.join(self.source_folder, f"file{i}.txt"),
                 f"content {i}")
            time.sleep(0.02)  # Small delay between files

        self.output.info("Sources ready")

    def build(self):
        # Read all source files
        for i in range(5):
            path = os.path.join(self.source_folder, f"file{i}.txt")
            if os.path.exists(path):
                content = load(self, path)
                self.output.info(f"File {i}: {content}")
            else:
                raise Exception(f"Source file {i} not found!")
"""
        setup_client.save({"conanfile.py": conanfile})

        # Export the recipe
        setup_client.run("export .")

        # Remove any existing source folder to force source() to run
        setup_client.run("remove * -c")
        setup_client.run("export .")

        # Create working directories for concurrent creates
        with tempfile.TemporaryDirectory() as workdir1, \
             tempfile.TemporaryDirectory() as workdir2:

            import shutil
            for workdir in [workdir1, workdir2]:
                shutil.copy(
                    os.path.join(setup_client.current_folder, "conanfile.py"),
                    os.path.join(workdir, "conanfile.py")
                )

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start 2 processes trying to build (and thus source) simultaneously
            processes = []
            for workdir in [workdir1, workdir2]:
                p = mp_context.Process(
                    target=_child_process_build_package,
                    args=(shared_cache, workdir, "srcpkg", result_queue)
                )
                processes.append(p)

            # Start both simultaneously
            for p in processes:
                p.start()

            # Wait for both to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 2, f"Should have 2 results, got {len(results)}"

            # Both processes should succeed with proper locking
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Build process {i} should succeed with proper source locking. " \
                    f"Error: {result.get('error', 'N/A')}"


@pytest.fixture
def shared_cache():
    """Fixture that provides a shared cache folder for multi-process tests."""
    with tempfile.TemporaryDirectory(prefix="conan_build_test_") as tmpdir:
        yield tmpdir
