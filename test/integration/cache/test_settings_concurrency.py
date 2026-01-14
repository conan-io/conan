"""
Tests for multi-process concurrent access to settings.yml.

These tests verify that settings.yml loading and migrations properly handle
concurrent access from multiple processes. Without proper locking, race conditions
can occur when multiple processes read or write settings.yml simultaneously.

Race conditions addressed:
1. Concurrent reads while another process is writing/migrating
2. Concurrent migrations from multiple processes
3. Read-modify-write races during config install operations
"""

import multiprocessing
import os
import tempfile
import textwrap
import threading
import time

import pytest
import yaml

from conan.test.utils.tools import TestClient
from test.utils.multiprocess import MultiProcessTestClient


# Helper function for concurrent settings operations - must be at module level
def _child_process_load_settings(cache_folder, result_queue, delay=0):
    """
    Child process that loads settings.yml.

    Args:
        cache_folder: Path to the cache folder
        result_queue: multiprocessing.Queue to report results
        delay: Optional delay before loading to stagger processes
    """
    try:
        if delay:
            time.sleep(delay)
        from conan.internal.model.settings import load_settings_yml
        settings = load_settings_yml(cache_folder)
        # Try to access a setting to ensure it's valid
        fields = settings.fields
        result_queue.put({"success": True, "fields": fields})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})


def _child_process_migrate_settings(cache_folder, result_queue, delay=0):
    """
    Child process that runs settings migration.

    Args:
        cache_folder: Path to the cache folder
        result_queue: multiprocessing.Queue to report results
        delay: Optional delay before migrating
    """
    try:
        if delay:
            time.sleep(delay)
        from conan.internal.default_settings import migrate_settings_file
        migrate_settings_file(cache_folder)
        result_queue.put({"success": True})
    except Exception as e:
        result_queue.put({"success": False, "error": str(e)})




class TestSettingsConcurrencyRaces:
    """
    Tests for concurrent settings.yml access.

    These tests verify that ConcurrencyLock properly protects settings.yml
    during concurrent reads and writes from multiple processes.
    """

    def test_concurrent_reads_during_write(self):
        """
        Test that reading settings.yml while another process writes doesn't cause corruption.

        Before fix: Readers may get corrupted YAML or incomplete data
        After fix: Readers wait for writer to finish, get consistent data
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache with settings
            client = TestClient(cache_folder=tmpdir)
            client.run("version")  # Initialize cache

            settings_path = os.path.join(tmpdir, "settings.yml")

            # Spawn processes: migrations (writers) and readers
            result_queue = multiprocessing.Queue()
            processes = []

            # Start readers immediately
            for i in range(5):
                p = multiprocessing.Process(
                    target=_child_process_load_settings,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Start migration (writer) with a tiny delay
            p = multiprocessing.Process(
                target=_child_process_migrate_settings,
                args=(tmpdir, result_queue, 0.001)
            )
            processes.append(p)
            p.start()

            # Wait for all processes
            for p in processes:
                p.join(timeout=30)
                if p.is_alive():
                    p.terminate()

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All operations should succeed without YAML errors
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some processes failed: {failures}"

            # Verify settings file is still valid
            with open(settings_path) as f:
                settings_data = yaml.safe_load(f)
                assert isinstance(settings_data, dict), "Settings file corrupted"

    def test_concurrent_migrations(self):
        """
        Test that concurrent migrations don't corrupt settings.yml.

        Before fix: Multiple processes migrating simultaneously can corrupt the file
        After fix: Migrations are serialized, only one process migrates at a time
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            # Spawn multiple processes all trying to migrate
            result_queue = multiprocessing.Queue()
            processes = []
            num_processes = 10

            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_child_process_migrate_settings,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=30)
                if p.is_alive():
                    p.terminate()

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some migrations failed: {failures}"

            # Settings should be valid
            settings_path = os.path.join(tmpdir, "settings.yml")
            with open(settings_path) as f:
                settings_data = yaml.safe_load(f)
                assert isinstance(settings_data, dict), "Settings file corrupted"

    def test_read_modify_write_race(self):
        """
        Test that concurrent config install operations don't corrupt settings.yml.

        This test demonstrates that config install operations that replace settings.yml
        are properly serialized with locks, preventing corruption during concurrent access.

        Before fix: Concurrent reads during writes could cause YAML errors
        After fix: Operations are serialized, file remains valid
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            # Create a custom settings file to install
            config_dir = os.path.join(tmpdir, "config_source")
            os.makedirs(config_dir)
            custom_settings = textwrap.dedent("""
                # This file was generated by Conan
                os:
                    CustomOS:
                        version: ["1.0", "2.0"]
                arch:
                    CustomArch: null
            """)
            with open(os.path.join(config_dir, "settings.yml"), "w") as f:
                f.write(custom_settings)

            # Spawn multiple processes doing config install simultaneously
            # This tests that the file locking prevents corruption
            result_queue = multiprocessing.Queue()
            processes = []
            num_processes = 5

            def _install_config(cache_folder, config_dir, result_queue):
                try:
                    from conan.test.utils.tools import TestClient
                    c = TestClient(cache_folder=cache_folder, light=True)
                    c.run(f"config install {config_dir}")
                    result_queue.put({"success": True})
                except Exception as e:
                    result_queue.put({"success": False, "error": str(e)})

            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_install_config,
                    args=(tmpdir, config_dir, result_queue)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=30)
                if p.is_alive():
                    p.terminate()

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed without YAML errors
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some config installs failed: {failures}"

            # Verify settings file is still valid and contains the expected data
            settings_path = os.path.join(tmpdir, "settings.yml")
            with open(settings_path) as f:
                settings_data = yaml.safe_load(f)
                assert isinstance(settings_data, dict), "Settings file corrupted"
                # The last config install should have won, file should have custom settings
                assert "CustomOS" in settings_data.get("os", {}), \
                    "Config install didn't properly update settings"


class TestSettingsConcurrencyStress:
    """
    Stress tests for settings concurrency with heavy load.
    """

    def test_heavy_concurrent_load(self):
        """
        Stress test with many processes reading and writing simultaneously.

        This test creates extreme concurrency pressure to expose race conditions
        by mixing migrations (writes) with settings loads (reads).
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            result_queue = multiprocessing.Queue()
            processes = []

            # Mix of readers and writers (migrations)
            num_readers = 20
            num_migrations = 5

            # Start readers
            for i in range(num_readers):
                p = multiprocessing.Process(
                    target=_child_process_load_settings,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Start migrations (writers)
            for i in range(num_migrations):
                p = multiprocessing.Process(
                    target=_child_process_migrate_settings,
                    args=(tmpdir, result_queue, 0.01 * i)
                )
                processes.append(p)
                p.start()

            # More readers
            for i in range(num_readers):
                p = multiprocessing.Process(
                    target=_child_process_load_settings,
                    args=(tmpdir, result_queue, 0.02)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=60)
                if p.is_alive():
                    p.terminate()

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # Count failures
            failures = [r for r in results if not r["success"]]

            # With proper locking, no operations should fail
            assert len(failures) == 0, \
                f"{len(failures)}/{len(results)} operations failed: {failures[:5]}"

            # Settings should still be valid
            settings_path = os.path.join(tmpdir, "settings.yml")
            with open(settings_path) as f:
                settings_data = yaml.safe_load(f)
                assert isinstance(settings_data, dict), "Settings file corrupted"


class TestSettingsUserConcurrency:
    """
    Tests for settings_user.yml concurrent access.

    The settings_user.yml file is merged with settings.yml on load,
    so it needs the same concurrency protection.
    """

    def test_concurrent_user_settings_read(self):
        """
        Test that reading settings with settings_user.yml doesn't have races.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            # Create settings_user.yml
            user_settings_path = os.path.join(tmpdir, "settings_user.yml")
            user_settings = textwrap.dedent("""
                user_os:
                    CustomOS:
                        version: ["1.0", "2.0"]
            """)
            with open(user_settings_path, "w") as f:
                f.write(user_settings)

            # Spawn multiple processes reading settings
            result_queue = multiprocessing.Queue()
            processes = []

            for i in range(10):
                p = multiprocessing.Process(
                    target=_child_process_load_settings,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=30)
                if p.is_alive():
                    p.terminate()

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some reads failed: {failures}"
