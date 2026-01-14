"""
Tests for concurrent access to global.conf during config install operations.

These tests verify that reading global.conf while another process is installing
a new global.conf via 'conan config install' doesn't cause corruption or race conditions.
"""

import multiprocessing
import os
import tempfile
import textwrap

import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.genconanfile import GenConanfile


def _child_process_read_global_conf(cache_folder, result_queue, delay=0):
    """
    Child process that reads global.conf.

    Args:
        cache_folder: Path to the cache folder
        result_queue: Queue to report results
        delay: Optional delay before reading
    """
    import time
    try:
        if delay:
            time.sleep(delay)

        from conan.internal.model.conf import load_global_conf
        conf = load_global_conf(cache_folder)

        # Try to access the internal structure to ensure it's valid
        # ConfDefinition has _pattern_confs attribute
        config_dict = dict(conf._pattern_confs)

        result_queue.put({
            "success": True,
            "config_count": len(config_dict),
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "error": str(e)
        })


def _child_process_config_install_global_conf(cache_folder, config_dir, result_queue):
    """
    Child process that installs global.conf via config install.

    Args:
        cache_folder: Path to the cache folder
        config_dir: Directory containing global.conf to install
        result_queue: Queue to report results
    """
    try:
        from conan.test.utils.tools import TestClient
        client = TestClient(cache_folder=cache_folder, light=True)
        client.run(f"config install {config_dir}")

        result_queue.put({
            "success": True,
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "error": str(e)
        })


class TestGlobalConfConcurrency:
    """
    Tests for concurrent global.conf access.

    These tests verify that config install operations that replace global.conf
    are properly serialized with locks, preventing corruption during concurrent
    read operations.
    """

    def test_concurrent_reads_during_config_install(self):
        """
        Test that reading global.conf while config install is writing doesn't cause corruption.

        Before fix: Readers may get corrupted or incomplete config
        After fix: Readers wait for writer to finish, get consistent data
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")  # Initialize cache with default global.conf

            # Create a config directory with custom global.conf
            config_dir = os.path.join(tmpdir, "config_source")
            os.makedirs(config_dir)
            custom_global_conf = textwrap.dedent("""
                # Custom configuration for testing
                core:non_interactive=True
                tools.cmake:version=3.20
                user.mycompany:setting=production
            """)
            with open(os.path.join(config_dir, "global.conf"), "w") as f:
                f.write(custom_global_conf)

            # Spawn processes: readers and config installers
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            # Start readers
            for i in range(5):
                p = mp_context.Process(
                    target=_child_process_read_global_conf,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Start config install (writer)
            p = mp_context.Process(
                target=_child_process_config_install_global_conf,
                args=(tmpdir, config_dir, result_queue)
            )
            processes.append(p)
            p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=30)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All operations should succeed without errors
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some operations failed: {failures}"

            # Verify global.conf is still valid
            from conan.internal.model.conf import load_global_conf
            final_conf = load_global_conf(tmpdir)
            assert final_conf is not None, "global.conf corrupted"

    def test_concurrent_config_installs(self):
        """
        Test that multiple concurrent config installs don't corrupt global.conf.

        Before fix: Concurrent writes can corrupt the file
        After fix: Writes are serialized with locks
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            # Create two different config directories
            config_dirs = []
            for i in range(2):
                config_dir = os.path.join(tmpdir, f"config_source_{i}")
                os.makedirs(config_dir)
                custom_conf = f"# Config {i}\ncore:non_interactive=True\nuser.test:value{i}=test{i}\n"
                with open(os.path.join(config_dir, "global.conf"), "w") as f:
                    f.write(custom_conf)
                config_dirs.append(config_dir)

            # Spawn multiple processes installing different configs
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for config_dir in config_dirs:
                p = mp_context.Process(
                    target=_child_process_config_install_global_conf,
                    args=(tmpdir, config_dir, result_queue)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=30)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some installs failed: {failures}"

            # Verify global.conf is still valid (one of the two configs should have won)
            from conan.internal.model.conf import load_global_conf
            final_conf = load_global_conf(tmpdir)
            assert final_conf is not None, "global.conf corrupted"

    def test_read_write_stress(self):
        """
        Stress test with many concurrent reads and writes.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize cache
            client = TestClient(cache_folder=tmpdir)
            client.run("version")

            # Create config directory
            config_dir = os.path.join(tmpdir, "config_source")
            os.makedirs(config_dir)
            custom_conf = "# Test\ncore:non_interactive=True\n"
            with open(os.path.join(config_dir, "global.conf"), "w") as f:
                f.write(custom_conf)

            # Spawn many readers and some writers
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            # Many readers
            for i in range(10):
                p = mp_context.Process(
                    target=_child_process_read_global_conf,
                    args=(tmpdir, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # A few writers
            for i in range(3):
                p = mp_context.Process(
                    target=_child_process_config_install_global_conf,
                    args=(tmpdir, config_dir, result_queue)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=60)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, \
                f"{len(failures)}/{len(results)} operations failed: {failures[:5]}"

            # Verify global.conf is still valid
            from conan.internal.model.conf import load_global_conf
            final_conf = load_global_conf(tmpdir)
            assert final_conf is not None, "global.conf corrupted"
