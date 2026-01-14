"""
Tests for multi-process concurrent access to profile operations.

These tests verify that profile operations (particularly profile detect)
are safe when multiple Conan processes access the same profile simultaneously.
"""

import os
import tempfile
import time

import pytest

from test.utils.multiprocess import MultiProcessTestClient


class TestProfileDetectConcurrency:
    """
    Integration tests for concurrent profile detect operations.

    These tests spawn actual Conan subprocesses to test real-world
    concurrent access scenarios for profile detection.
    """

    @pytest.fixture
    def shared_cache(self):
        """Create a temporary shared cache folder"""
        with tempfile.TemporaryDirectory(prefix="conan_test_") as tmpdir:
            yield tmpdir

    def test_concurrent_profile_detect_same_name(self, shared_cache):
        """
        Test that multiple processes can safely run profile detect for the same profile.

        Race scenario without locks:
        - Process 1 checks file doesn't exist → proceeds
        - Process 2 checks file doesn't exist → proceeds
        - Process 1 writes profile
        - Process 2 overwrites Process 1's profile
        - Result: File corruption or lost writes

        With proper locking, all processes should:
        - Serialize access to the profile file
        - Only one process creates the file
        - Others see it already exists and skip (with --exist-ok)
        """
        client = MultiProcessTestClient(shared_cache)

        # Run 10 concurrent profile detect commands with --exist-ok
        # This should be safe - first one creates, rest skip
        commands = [
            ["profile", "detect", "--name=default", "--exist-ok"]
            for _ in range(10)
        ]

        results = client.run_concurrent(commands, max_workers=10, timeout=60)

        # All commands should succeed
        for i, result in enumerate(results):
            assert result.returncode == 0, (
                f"Process {i} failed with:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Profile file should exist and be valid
        profile_path = os.path.join(shared_cache, "profiles", "default")
        assert os.path.exists(profile_path), "Profile was not created"

        # Profile should be readable and have expected structure
        with open(profile_path, "r") as f:
            content = f.read()
            # Should have at least the basic sections
            assert "[settings]" in content, "Profile missing [settings] section"

    def test_concurrent_profile_detect_without_exist_ok(self, shared_cache):
        """
        Test concurrent profile detect without --exist-ok flag.

        Without --exist-ok and without proper locking, this could:
        1. Cause file corruption if processes write simultaneously
        2. Fail with confusing errors if process 2 sees file created by process 1

        With proper locking:
        - First process creates the profile
        - Subsequent processes should get a clear error that it already exists
          (unless they started before the first one finished)
        """
        client = MultiProcessTestClient(shared_cache)

        # Run 5 concurrent profile detect commands without --exist-ok
        commands = [
            ["profile", "detect", "--name=default"]
            for _ in range(5)
        ]

        results = client.run_concurrent(commands, max_workers=5, timeout=60)

        # At least one should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count >= 1, "At least one process should have created the profile"

        # The rest should fail with "already exists" error
        # (unless they all started before the first one checked)
        failed_count = sum(1 for r in results if r.returncode != 0)
        if failed_count > 0:
            # Check that failures are due to "already exists"
            for result in results:
                if result.returncode != 0:
                    assert "already exists" in result.stderr or "already exists" in result.stdout, (
                        f"Unexpected error: {result.stderr}"
                    )

        # Profile file should exist and be valid (not corrupted)
        profile_path = os.path.join(shared_cache, "profiles", "default")
        assert os.path.exists(profile_path), "Profile was not created"

        # Profile should be readable and have expected structure
        with open(profile_path, "r") as f:
            content = f.read()
            assert "[settings]" in content, "Profile appears corrupted"

    def test_concurrent_profile_detect_with_force(self, shared_cache):
        """
        Test concurrent profile detect with --force flag.

        This is the most dangerous scenario without locking:
        - Multiple processes trying to overwrite the same file
        - Could result in corrupted or partial file contents

        With proper locking:
        - Writes are serialized
        - File remains valid after all processes complete
        """
        client = MultiProcessTestClient(shared_cache)

        # First create the profile
        result = client.run_conan(["profile", "detect", "--name=test_force"])
        assert result.returncode == 0, f"Initial profile creation failed: {result.stderr}"

        # Now run multiple concurrent overwrites with --force
        commands = [
            ["profile", "detect", "--name=test_force", "--force"]
            for _ in range(8)
        ]

        results = client.run_concurrent(commands, max_workers=8, timeout=60)

        # All should succeed (they all have --force)
        for i, result in enumerate(results):
            assert result.returncode == 0, (
                f"Process {i} failed with:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Profile file should still be valid (not corrupted)
        profile_path = os.path.join(shared_cache, "profiles", "test_force")
        assert os.path.exists(profile_path), "Profile was deleted"

        # Profile should be readable and complete
        with open(profile_path, "r") as f:
            content = f.read()
            # Should have complete profile structure
            assert "[settings]" in content, "Profile appears corrupted"
            # Should not have partial writes or duplicate sections
            assert content.count("[settings]") == 1, "Profile has duplicate sections"

    def test_concurrent_profile_detect_different_names(self, shared_cache):
        """
        Test concurrent profile detect with different profile names.

        Even without fine-grained locking, this should work if locks are
        per-profile (not a global profiles lock).
        """
        client = MultiProcessTestClient(shared_cache)

        # Run concurrent detects for different profiles
        profile_names = [f"profile_{i}" for i in range(10)]
        commands = [
            ["profile", "detect", f"--name={name}"]
            for name in profile_names
        ]

        results = client.run_concurrent(commands, max_workers=10, timeout=60)

        # All should succeed
        for i, result in enumerate(results):
            assert result.returncode == 0, (
                f"Process {i} (profile {profile_names[i]}) failed with:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # All profile files should exist
        for name in profile_names:
            profile_path = os.path.join(shared_cache, "profiles", name)
            assert os.path.exists(profile_path), f"Profile {name} was not created"

            with open(profile_path, "r") as f:
                content = f.read()
                assert "[settings]" in content, f"Profile {name} appears corrupted"

    def test_concurrent_profile_detect_subdirectory(self, shared_cache):
        """
        Test concurrent profile detect with profile in subdirectory.

        This tests the directory creation race:
        - Process 1 checks dir doesn't exist
        - Process 2 checks dir doesn't exist
        - Both call makedirs
        - Both write files

        With proper locking and exist_ok=True, this should work.
        """
        client = MultiProcessTestClient(shared_cache)

        # Run concurrent detects for profiles in the same subdirectory
        commands = [
            ["profile", "detect", "--name=mydir/profile", "--exist-ok"]
            for _ in range(5)
        ]

        results = client.run_concurrent(commands, max_workers=5, timeout=60)

        # All should succeed
        for i, result in enumerate(results):
            assert result.returncode == 0, (
                f"Process {i} failed with:\n"
                f"stdout: {result.stdout}\n"
                f"stderr: {result.stderr}"
            )

        # Profile should exist in subdirectory
        profile_path = os.path.join(shared_cache, "profiles", "mydir", "profile")
        assert os.path.exists(profile_path), "Profile in subdirectory was not created"

        with open(profile_path, "r") as f:
            content = f.read()
            assert "[settings]" in content, "Profile appears corrupted"

    def test_profile_detect_file_integrity_under_load(self, shared_cache):
        """
        Stress test: verify profile file integrity under heavy concurrent load.

        This test creates multiple profiles concurrently and verifies that
        all files are complete and valid after the operations.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create 20 different profiles concurrently
        # Each profile is created 3 times (first creates, others should fail or be exist-ok)
        commands = []
        profile_names = [f"stress_{i}" for i in range(20)]
        for name in profile_names:
            # First attempt without exist-ok (should create)
            commands.append(["profile", "detect", f"--name={name}"])
            # Second and third with exist-ok (should skip)
            commands.append(["profile", "detect", f"--name={name}", "--exist-ok"])
            commands.append(["profile", "detect", f"--name={name}", "--exist-ok"])

        # Run all 60 commands concurrently
        results = client.run_concurrent(commands, max_workers=20, timeout=120)

        # Verify all profile files exist and are valid
        for name in profile_names:
            profile_path = os.path.join(shared_cache, "profiles", name)
            assert os.path.exists(profile_path), f"Profile {name} was not created"

            with open(profile_path, "r") as f:
                content = f.read()
                # Basic validation
                assert len(content) > 0, f"Profile {name} is empty"
                assert "[settings]" in content, f"Profile {name} missing [settings] section"
                assert content.count("[settings]") == 1, f"Profile {name} has duplicate sections"
                # Should not have truncated or corrupted data
                assert not content.endswith("["), f"Profile {name} appears truncated"
                assert not content.endswith("="), f"Profile {name} appears truncated"

    def test_profile_detect_atomic_write(self, shared_cache):
        """
        Test that profile writes are atomic (no partial files visible).

        Without atomic writes (temp file + rename), concurrent processes
        might see partial file contents or corrupted data.
        """
        client = MultiProcessTestClient(shared_cache)

        # Run many concurrent profile detects
        commands = [
            ["profile", "detect", "--name=atomic_test", "--force"]
            for _ in range(15)
        ]

        results = client.run_concurrent(commands, max_workers=15, timeout=60)

        # All should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 15, f"Only {success_count}/15 processes succeeded"

        # Final profile should be complete and valid
        profile_path = os.path.join(shared_cache, "profiles", "atomic_test")
        assert os.path.exists(profile_path)

        with open(profile_path, "r") as f:
            content = f.read()
            # Should be a complete, valid profile
            assert "[settings]" in content
            # Should have typical profile structure (settings, not truncated)
            lines = content.strip().split("\n")
            assert len(lines) > 1, "Profile appears incomplete"

        # There should be no .tmp files left behind
        profiles_dir = os.path.join(shared_cache, "profiles")
        tmp_files = [f for f in os.listdir(profiles_dir) if f.endswith(".tmp")]
        assert len(tmp_files) == 0, f"Found leftover .tmp files: {tmp_files}"
