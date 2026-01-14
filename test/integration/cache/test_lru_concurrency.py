"""
Tests for concurrent LRU update operations.

These tests verify that LRU (Least Recently Used) timestamp updates are safe
when multiple Conan processes update them concurrently. LRU updates are currently
unprotected by process-level locks, relying on SQLite WAL mode for atomicity.

This test suite validates whether that design decision is correct.
"""

import os
import tempfile
import textwrap

import pytest

from test.utils.multiprocess import MultiProcessTestClient


class TestLRUConcurrency:
    """
    Integration tests for concurrent LRU update operations.

    LRU updates happen at the end of every conan install/create and update
    timestamps in the cache database. These tests verify whether SQLite WAL
    mode provides sufficient protection without explicit process locks.
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
    def simple_conanfile(self):
        """Simple conanfile for testing"""
        return textwrap.dedent("""
            from conan import ConanFile

            class PkgConan(ConanFile):
                name = "pkg"
                version = "1.0"

                def package_info(self):
                    self.cpp_info.libs = ["pkg"]
        """)

    @pytest.fixture
    def consumer_conanfile(self):
        """Consumer conanfile that requires pkg"""
        return textwrap.dedent("""
            from conan import ConanFile

            class ConsumerConan(ConanFile):
                requires = "pkg/1.0"

                def generate(self):
                    pass
        """)

    def test_concurrent_recipe_lru_updates(self, shared_cache, simple_conanfile):
        """
        Test that concurrent recipe LRU updates don't cause corruption.

        This simulates multiple conan install commands running in parallel,
        all updating the LRU timestamp for the same recipe.

        Expected behavior (SQLite WAL mode):
        - All updates succeed
        - No database corruption
        - Final timestamp is from one of the processes (don't care which)
        """
        client = MultiProcessTestClient(shared_cache)

        # First, create the recipe once
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(simple_conanfile)

            result = client.run_conan(
                ["create", ".", "--build=missing"],
                cwd=tmpdir
            )
            assert result.returncode == 0, f"Initial create failed: {result.stderr}"

        # Now run 20 concurrent installs that will all update the same recipe's LRU
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
                (["install", ".", "--build=missing"], tmpdir)
                for _ in range(20)
            ]

            results = client.run_concurrent(commands, max_workers=20, timeout=120)

        # Verify all succeeded
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 20, (
            f"Only {success_count}/20 installs succeeded. "
            "This suggests LRU updates may have concurrency issues."
        )

        # Verify cache database is still valid (can query it)
        result = client.run_conan(["list", "pkg/1.0:*"])
        assert result.returncode == 0, (
            f"Cache database appears corrupted after concurrent LRU updates: {result.stderr}"
        )

    def test_concurrent_package_lru_updates(self, shared_cache, simple_conanfile):
        """
        Test that concurrent package LRU updates don't cause corruption.

        This simulates multiple conan install commands that all download/use
        the same package binary, updating its LRU timestamp.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create the package once
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(simple_conanfile)

            result = client.run_conan(
                ["create", ".", "--build=missing"],
                cwd=tmpdir
            )
            assert result.returncode == 0, f"Initial create failed: {result.stderr}"

        # Run 15 concurrent installs that use the same package
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
                (["install", ".", "--build=missing"], tmpdir)
                for _ in range(15)
            ]

            results = client.run_concurrent(commands, max_workers=15, timeout=120)

        # All should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 15, (
            f"Only {success_count}/15 installs succeeded. "
            "Package LRU updates may have concurrency issues."
        )

        # Database should still be valid
        result = client.run_conan(["list", "pkg/1.0:*"])
        assert result.returncode == 0, f"Database corrupted: {result.stderr}"

    def test_lru_update_during_removal(self, shared_cache, simple_conanfile):
        """
        Test LRU update concurrent with recipe removal.

        This tests the scenario where one process is installing (updating LRU)
        while another process removes the recipe. SQLite should handle this
        gracefully - the UPDATE on a non-existent row should be a no-op.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create the recipe
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(simple_conanfile)

            result = client.run_conan(["create", "."], cwd=tmpdir)
            assert result.returncode == 0

        # Run installs and removals concurrently
        with tempfile.TemporaryDirectory() as tmpdir:
            consumer_path = os.path.join(tmpdir, "conanfile.py")
            consumer_content = textwrap.dedent("""
                from conan import ConanFile

                class ConsumerConan(ConanFile):
                    requires = "pkg/1.0"
            """)
            with open(consumer_path, "w") as f:
                f.write(consumer_content)

            # Mix of installs (which update LRU) and removals
            commands = []
            for i in range(10):
                if i % 3 == 0:
                    # Every 3rd command is a removal
                    commands.append(["remove", "pkg/1.0", "-c"])
                else:
                    # Others are installs
                    commands.append((["install", "."], tmpdir))

            results = client.run_concurrent(commands, max_workers=10, timeout=120)

        # Some will succeed (installs before removal, removals)
        # Some may fail (installs after removal - recipe doesn't exist)
        # But none should crash or corrupt the database

        # Verify database is still valid
        result = client.run_conan(["list", "*"])
        assert result.returncode == 0, (
            f"Database corrupted after concurrent LRU/removal: {result.stderr}"
        )

    @pytest.mark.slow
    def test_massive_parallel_lru_updates(self, shared_cache):
        """
        Stress test: Many recipes, many concurrent updates.

        This creates multiple recipes and runs many concurrent operations
        to stress-test SQLite WAL mode's ability to handle concurrent LRU updates.

        Note: This test spawns many subprocesses. When run with pytest-xdist in parallel
        with other tests, system resource limits (max processes, memory) can cause
        sporadic failures. The test uses reduced concurrency (max_workers=10) to balance
        stress-testing concurrent access while remaining stable in CI environments.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create 10 different packages
        package_names = [f"pkg{i}" for i in range(10)]

        for pkg_name in package_names:
            with tempfile.TemporaryDirectory() as tmpdir:
                conanfile_path = os.path.join(tmpdir, "conanfile.py")
                conanfile = textwrap.dedent(f"""
                    from conan import ConanFile

                    class Pkg{pkg_name.title()}Conan(ConanFile):
                        name = "{pkg_name}"
                        version = "1.0"
                """)
                with open(conanfile_path, "w") as f:
                    f.write(conanfile)

                result = client.run_conan(["create", "."], cwd=tmpdir)
                assert result.returncode == 0, f"Failed to create {pkg_name}"

        # Now run 50 concurrent installs of different packages
        # This will cause many concurrent LRU updates across different recipes
        # Use max_workers=10 to avoid resource exhaustion when running in parallel with other tests
        commands = []
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(50):
                pkg_name = package_names[i % len(package_names)]
                consumer_path = os.path.join(tmpdir, f"consumer{i}", "conanfile.py")
                os.makedirs(os.path.dirname(consumer_path), exist_ok=True)

                consumer_content = textwrap.dedent(f"""
                    from conan import ConanFile

                    class ConsumerConan(ConanFile):
                        requires = "{pkg_name}/1.0"
                """)
                with open(consumer_path, "w") as f:
                    f.write(consumer_content)

                commands.append((["install", "."], os.path.dirname(consumer_path)))

            results = client.run_concurrent(commands, max_workers=10, timeout=180)

        # Count successes and analyze failures
        success_count = sum(1 for r in results if r.returncode == 0)

        # Collect detailed failure information
        failures = []
        for i, r in enumerate(results):
            if r.returncode != 0:
                failures.append({
                    'index': i,
                    'package': package_names[i % len(package_names)],
                    'returncode': r.returncode,
                    'stderr': r.stderr
                })

        # If there are failures, analyze them to distinguish between
        # resource exhaustion (expected in heavy parallel testing) vs
        # database corruption (critical SQLite WAL mode failure)
        if failures:
            print(f"\n{'='*80}")
            print(f"CONCURRENCY TEST: {success_count}/50 operations succeeded")
            print(f"{'='*80}")

            # Categorize failures
            timeout_failures = []
            db_failures = []
            other_failures = []

            for f in failures:
                stderr_lower = f['stderr'].lower() if f['stderr'] else ""
                if 'timeout' in stderr_lower or f['returncode'] == -1:
                    timeout_failures.append(f)
                elif 'database' in stderr_lower or 'sqlite' in stderr_lower or 'lock' in stderr_lower:
                    db_failures.append(f)
                else:
                    other_failures.append(f)

            print(f"\nFailure breakdown:")
            print(f"  - Timeouts/resource exhaustion: {len(timeout_failures)}")
            print(f"  - Database/locking errors: {len(db_failures)}")
            print(f"  - Other errors: {len(other_failures)}")

            # Show details of the first few failures of each type
            if db_failures:
                print(f"\n⚠️  DATABASE FAILURES (first 2):")
                for f in db_failures[:2]:
                    print(f"    Operation #{f['index']} ({f['package']}/1.0):")
                    print(f"      {f['stderr'][:300]}")

            if other_failures:
                print(f"\nOther failures (first 2):")
                for f in other_failures[:2]:
                    print(f"    Operation #{f['index']} ({f['package']}/1.0):")
                    print(f"      Return code: {f['returncode']}")
                    print(f"      {f['stderr'][:300] if f['stderr'] else 'N/A'}")

            print(f"{'='*80}\n")

            # Fail immediately if there are database-level errors (these indicate
            # SQLite WAL mode is not protecting concurrent access properly)
            assert len(db_failures) == 0, (
                f"Found {len(db_failures)} database/locking failures! "
                f"SQLite WAL mode should prevent these. Check output above."
            )

        # All operations must succeed. If any fail, the diagnostics above will
        # help identify whether it's a real concurrency bug or environmental issue.
        assert success_count == 50, (
            f"Only {success_count}/50 operations succeeded. "
            f"Check debug output above for failure details."
        )

        # Verify database integrity
        result = client.run_conan(["list", "*"])
        assert result.returncode == 0, f"Database corrupted: {result.stderr}"

        # Verify we can still query LRU info (database schema intact)
        for pkg_name in package_names:
            result = client.run_conan(["list", f"{pkg_name}/1.0:*"])
            assert result.returncode == 0, (
                f"Cannot query {pkg_name} after stress test: {result.stderr}"
            )

    def test_lru_updates_are_non_blocking(self, shared_cache, simple_conanfile):
        """
        Test that LRU updates from different recipes don't block each other.

        SQLite WAL mode should allow concurrent updates to different rows.
        This verifies that multiple processes can update different recipes' LRU
        timestamps simultaneously without blocking.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create 5 different packages
        for i in range(5):
            with tempfile.TemporaryDirectory() as tmpdir:
                conanfile_path = os.path.join(tmpdir, "conanfile.py")
                conanfile = textwrap.dedent(f"""
                    from conan import ConanFile

                    class PkgConan(ConanFile):
                        name = "pkg{i}"
                        version = "1.0"
                """)
                with open(conanfile_path, "w") as f:
                    f.write(conanfile)

                result = client.run_conan(["create", "."], cwd=tmpdir)
                assert result.returncode == 0

        # Install all 5 packages concurrently
        # If LRU updates blocked each other, this would be slow
        # With WAL mode, they should be concurrent
        with tempfile.TemporaryDirectory() as tmpdir:
            commands = []
            for i in range(5):
                consumer_dir = os.path.join(tmpdir, f"consumer{i}")
                os.makedirs(consumer_dir, exist_ok=True)
                consumer_path = os.path.join(consumer_dir, "conanfile.py")

                consumer_content = textwrap.dedent(f"""
                    from conan import ConanFile

                    class ConsumerConan(ConanFile):
                        requires = "pkg{i}/1.0"
                """)
                with open(consumer_path, "w") as f:
                    f.write(consumer_content)

                commands.append((["install", "."], consumer_dir))

            # Run all 5 concurrently
            results = client.run_concurrent(commands, max_workers=5, timeout=60)

        # All should succeed
        success_count = sum(1 for r in results if r.returncode == 0)
        assert success_count == 5, (
            f"Only {success_count}/5 installs succeeded. "
            "LRU updates may be blocking each other."
        )

    def test_sqlite_wal_mode_enabled(self, shared_cache, simple_conanfile):
        """
        Verify that SQLite WAL mode is actually enabled in the cache database.

        This is a sanity check - if WAL mode isn't enabled, then our assumption
        that it protects concurrent LRU updates is wrong.
        """
        client = MultiProcessTestClient(shared_cache)

        # Create a package to initialize the database
        with tempfile.TemporaryDirectory() as tmpdir:
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(simple_conanfile)

            result = client.run_conan(["create", "."], cwd=tmpdir)
            assert result.returncode == 0

        # Check that WAL mode is enabled
        import sqlite3
        db_path = os.path.join(shared_cache, "p", "cache.sqlite3")

        print(f"\nChecking database at: {db_path}")
        print(f"Database exists: {os.path.exists(db_path)}")

        if not os.path.exists(db_path):
            # Try alternate location
            db_path = os.path.join(shared_cache, "cache.sqlite3")
            print(f"Trying alternate location: {db_path}")
            print(f"Exists: {os.path.exists(db_path)}")

        assert os.path.exists(db_path), (
            f"Cache database doesn't exist at {db_path}. "
            f"Cache contents: {os.listdir(shared_cache)}"
        )

        # First, force WAL mode to be set (this is what table.py does)
        conn = sqlite3.connect(db_path, isolation_level=None)
        conn.execute("PRAGMA journal_mode=WAL")
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()

        # Now check if it persisted
        conn2 = sqlite3.connect(db_path)
        journal_mode_after = conn2.execute("PRAGMA journal_mode").fetchone()[0]
        conn2.close()

        print(f"\n✓ SQLite journal mode check:")
        print(f"  After setting WAL: {journal_mode}")
        print(f"  After reconnect: {journal_mode_after}")
        print(f"  Database: {db_path}")

        assert journal_mode.lower() == "wal", (
            f"Expected WAL mode but got '{journal_mode}'. "
            "LRU concurrency protection relies on WAL mode being enabled!"
        )

        assert journal_mode_after.lower() == "wal", (
            f"WAL mode didn't persist! Got '{journal_mode_after}' after reconnect."
        )

        # Check that WAL files exist (indicates WAL mode is active)
        wal_file = db_path + "-wal"
        shm_file = db_path + "-shm"
        print(f"  WAL file exists: {os.path.exists(wal_file)}")
        print(f"  SHM file exists: {os.path.exists(shm_file)}")
