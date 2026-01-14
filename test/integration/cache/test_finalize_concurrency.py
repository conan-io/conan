"""
Tests for concurrent finalize folder creation.

These tests verify that the finalize() method execution is safe when multiple
Conan processes try to finalize the same package simultaneously.

The finalize() method is a user-defined method that runs after package() but
before package_info(). It creates a "finalize folder" where users can customize
package contents per-installation. Without proper locking, concurrent finalize()
calls can corrupt files.
"""

import glob
import os
import shutil
import tempfile
import textwrap
import time

import pytest

from test.utils.multiprocess import MultiProcessTestClient


class TestFinalizeConcurrency:
    """
    Integration tests for concurrent finalize folder creation.

    The finalize() method allows packages to customize their contents after
    being built/downloaded. When multiple processes install the same package
    for the first time, they race to create and populate the finalize folder.
    """

    @pytest.fixture
    def shared_cache(self):
        """Create a temporary shared cache folder with default profile"""
        with tempfile.TemporaryDirectory(prefix="conan_test_") as tmpdir:
            # Create default profile so conan commands can run
            client = MultiProcessTestClient(tmpdir)
            result = client.run_conan(["profile", "detect"])
            assert result.returncode == 0, f"Failed to create default profile: {result.stderr}"
            yield tmpdir

    @pytest.fixture
    def finalize_conanfile(self):
        """Conanfile with finalize() method that writes files"""
        return textwrap.dedent("""
            import os
            import time
            from conan import ConanFile
            from conan.tools.files import save, copy

            class PkgConan(ConanFile):
                name = "pkg"
                version = "1.0"

                def package(self):
                    # Create some files in the immutable package folder
                    save(self, os.path.join(self.package_folder, "original.txt"),
                         "Original file from package()")

                def finalize(self):
                    # This is where the race condition occurs
                    # Multiple processes might execute this simultaneously
                    pid = os.getpid()
                    self.output.info(f"[PID {pid}] Starting finalize")

                    # Write a marker file with PID - if multiple processes run, we'll see multiple files
                    marker_file = os.path.join(self.package_folder, f"finalize_started_{pid}.marker")
                    save(self, marker_file, f"Started by {pid}")

                    # Copy from immutable to finalize folder
                    copy(self, "original.txt",
                         src=self.immutable_package_folder,
                         dst=self.package_folder)

                    # Simulate work to make race window larger
                    time.sleep(0.2)

                    # Write a completion marker
                    done_marker = os.path.join(self.package_folder, f"finalize_done_{pid}.marker")
                    save(self, done_marker, f"Completed by {pid}")

                    # Increment a shared counter - this is the race detector
                    # If multiple processes run finalize(), this will show count > 1
                    counter_file = os.path.join(self.package_folder, "finalize_count.txt")

                    # Read-modify-write without locking - creates race condition
                    if os.path.exists(counter_file):
                        with open(counter_file, "r") as f:
                            count = int(f.read().strip())
                        time.sleep(0.05)  # Make race more likely
                        save(self, counter_file, str(count + 1))
                    else:
                        save(self, counter_file, "1")

                    self.output.info(f"[PID {pid}] Finished finalize")

                def package_info(self):
                    self.output.info(f"package_info in {self.package_folder}")
        """)

    def test_concurrent_finalize_folder_creation(self, shared_cache, finalize_conanfile):
        """
        Test that concurrent finalize() calls don't corrupt the finalize folder.

        Race scenario without locks:
        1. Process A checks: finalize folder doesn't exist
        2. Process B checks: finalize folder doesn't exist
        3. Process A creates folder and runs finalize()
        4. Process B creates folder and runs finalize() <-- CONCURRENT EXECUTION
        5. Both processes write to the same files --> CORRUPTION

        Expected behavior with proper locking:
        - Only one process creates and populates the finalize folder
        - Other processes wait until the first one finishes
        - The finalize folder contains valid, uncorrupted files
        """
        client = MultiProcessTestClient(shared_cache)

        # First, create the package in the cache
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(finalize_conanfile)

            result = client.run_conan(["create", "."], cwd=tmpdir)
            assert result.returncode == 0, f"Package creation failed: {result.stderr}"

        # Now remove the finalize folder to simulate first-time install after download
        # This is the key: we want multiple processes to hit the "finalize folder doesn't exist" path
        # The cache structure is: {cache}/p/{pkg_name}/{hash}/p/{package_id}/{package_rev}/f
        finalize_folder_pattern = os.path.join(shared_cache, "p", "**", "f")
        finalize_folders = glob.glob(finalize_folder_pattern, recursive=True)

        # Debug: print what we found
        if len(finalize_folders) == 0:
            # Try to find what's actually in the cache
            cache_structure = []
            for root, dirs, files in os.walk(shared_cache):
                if "f" in dirs:
                    cache_structure.append(os.path.join(root, "f"))
            if cache_structure:
                finalize_folder = cache_structure[0]
            else:
                # Finalize folder might not exist yet on first create
                # In that case, we'll need to run an install first
                pytest.skip("Finalize folder not created yet - this is expected for first create")
        else:
            finalize_folder = finalize_folders[0]

        if os.path.exists(finalize_folder):
            print(f"\n[TEST] Deleting finalize folder: {finalize_folder}")
            print(f"[TEST] Contents before deletion: {os.listdir(finalize_folder)}")
            shutil.rmtree(finalize_folder)
            assert not os.path.exists(finalize_folder), "Finalize folder should be deleted"
            print(f"[TEST] Finalize folder deleted successfully")
        else:
            print(f"\n[TEST] Finalize folder doesn't exist yet: {finalize_folder}")

        # Run 20 concurrent installs - they should all race to create finalize folder
        # Use more processes to increase likelihood of race
        print(f"[TEST] Starting 20 concurrent installs...")
        with tempfile.TemporaryDirectory() as tmpdir:
            consumer_path = os.path.join(tmpdir, "conanfile.py")
            consumer_content = textwrap.dedent("""
                from conan import ConanFile

                class ConsumerConan(ConanFile):
                    requires = "pkg/1.0"
            """)
            with open(consumer_path, "w") as f:
                f.write(consumer_content)

            commands = [
                (["install", "."], tmpdir)
                for _ in range(20)
            ]

            results = client.run_concurrent(commands, max_workers=20, timeout=180)

        # All should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 20, (
            f"Only {success_count}/20 installs succeeded. "
            "Finalize concurrency may have issues."
        )

        # Verify finalize folder exists and is valid
        assert os.path.exists(finalize_folder), "Finalize folder should exist after installs"

        # Check how many marker files exist - each process that ran finalize() creates one
        all_files = os.listdir(finalize_folder)
        marker_files = [f for f in all_files if f.startswith("finalize_started_")]
        num_processes_that_ran = len(marker_files)

        print(f"\n[TEST] After concurrent installs:")
        print(f"[TEST] Finalize folder contents: {all_files}")
        print(f"[TEST] Marker files found: {marker_files}")
        print(f"[TEST] Number of processes that ran finalize(): {num_processes_that_ran}")

        # Check the counter file - without proper locking, this might be > 1
        # indicating multiple processes ran finalize()
        counter_file = os.path.join(finalize_folder, "finalize_count.txt")
        if os.path.exists(counter_file):
            with open(counter_file, "r") as f:
                counter = int(f.read().strip())

            # With proper locking, counter should be exactly 1
            # (only one process should have executed finalize())
            assert counter == 1, (
                f"Counter is {counter}, expected 1. "
                f"This indicates {counter} processes executed finalize() concurrently! "
                f"Found {num_processes_that_ran} marker files: {marker_files}"
            )

            # Also verify that only one process ran
            assert num_processes_that_ran == 1, (
                f"Found {num_processes_that_ran} processes that ran finalize(), expected 1. "
                f"Marker files: {marker_files}. This is a race condition!"
            )

        # Verify files are complete and not corrupted
        assert os.path.exists(os.path.join(finalize_folder, "original.txt")), \
            "original.txt should exist in finalize folder"

    def test_concurrent_finalize_different_packages(self, shared_cache):
        """
        Test that finalize() for different packages don't block each other.

        This verifies that locking is per-package, not global.
        Different packages should be able to finalize concurrently.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create 3 different packages with finalize()
        for i in range(3):
            with tempfile.TemporaryDirectory() as tmpdir:
                conanfile_path = os.path.join(tmpdir, "conanfile.py")
                conanfile = textwrap.dedent(f"""
                    import os
                    from conan import ConanFile
                    from conan.tools.files import save

                    class Pkg{i}Conan(ConanFile):
                        name = "pkg{i}"
                        version = "1.0"

                        def package(self):
                            save(self, os.path.join(self.package_folder, "file.txt"), "data")

                        def finalize(self):
                            save(self, os.path.join(self.package_folder, "finalized.txt"),
                                 "finalized by pkg{i}")
                """)
                with open(conanfile_path, "w") as f:
                    f.write(conanfile)

                result = client.run_conan(["create", "."], cwd=tmpdir)
                assert result.returncode == 0, f"pkg{i} creation failed"

        # Remove all finalize folders
        finalize_folders = glob.glob(os.path.join(shared_cache, "p", "**", "f"), recursive=True)
        for folder in finalize_folders:
            if os.path.exists(folder):
                shutil.rmtree(folder)

        # Install all 3 packages concurrently
        with tempfile.TemporaryDirectory() as tmpdir:
            commands = []
            for i in range(3):
                consumer_dir = os.path.join(tmpdir, f"consumer{i}")
                os.makedirs(consumer_dir)
                consumer_path = os.path.join(consumer_dir, "conanfile.py")
                consumer_content = textwrap.dedent(f"""
                    from conan import ConanFile

                    class ConsumerConan(ConanFile):
                        requires = "pkg{i}/1.0"
                """)
                with open(consumer_path, "w") as f:
                    f.write(consumer_content)

                commands.append((["install", "."], consumer_dir))

            results = client.run_concurrent(commands, max_workers=3, timeout=60)

        # All should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 3, (
            f"Only {success_count}/3 installs succeeded. "
            "Different packages should not block each other's finalize()."
        )

    def test_finalize_folder_already_exists(self, shared_cache, finalize_conanfile):
        """
        Test that if finalize folder already exists, finalize() is not called again.

        This is the normal case - first install creates finalize folder,
        subsequent installs should skip finalize() and just use existing folder.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create the package
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(finalize_conanfile)

            result = client.run_conan(["create", "."], cwd=tmpdir)
            assert result.returncode == 0

        # Get the counter value after first finalize
        finalize_folders = glob.glob(os.path.join(shared_cache, "p", "**", "f"), recursive=True)
        assert len(finalize_folders) > 0, "Finalize folder should exist after create"
        finalize_folder = finalize_folders[0]
        counter_file = os.path.join(finalize_folder, "finalize_count.txt")

        with open(counter_file, "r") as f:
            initial_counter = int(f.read().strip())

        assert initial_counter == 1, "Initial counter should be 1"

        # Count initial marker files
        initial_markers = len([f for f in os.listdir(finalize_folder)
                              if f.startswith("finalize_started_")])

        # Run multiple installs - they should NOT call finalize() again
        with tempfile.TemporaryDirectory() as tmpdir:
            consumer_path = os.path.join(tmpdir, "conanfile.py")
            consumer_content = textwrap.dedent("""
                from conan import ConanFile

                class ConsumerConan(ConanFile):
                    requires = "pkg/1.0"
            """)
            with open(consumer_path, "w") as f:
                f.write(consumer_content)

            # Run 5 installs
            for _ in range(5):
                result = client.run_conan(["install", "."], cwd=tmpdir)
                assert result.returncode == 0

        # Counter should still be 1 - finalize() should not have run again
        with open(counter_file, "r") as f:
            final_counter = int(f.read().strip())

        final_markers = len([f for f in os.listdir(finalize_folder)
                            if f.startswith("finalize_started_")])

        assert final_counter == 1, (
            f"Counter changed from {initial_counter} to {final_counter}. "
            "finalize() should only run once when folder already exists."
        )

        assert final_markers == initial_markers, (
            f"Marker count changed from {initial_markers} to {final_markers}. "
            "finalize() should not have run again."
        )
