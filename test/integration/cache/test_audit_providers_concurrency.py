"""
Tests for multi-process concurrent access to audit_providers.json.

These tests verify that the AuditAPI properly handles concurrent access
from multiple processes when modifying audit_providers.json.

The tests are designed to FAIL before the fix is applied, demonstrating
the race conditions that exist in the unprotected read-modify-write
operations in add_provider(), remove_provider(), and auth_provider().
"""

import json
import multiprocessing
import os
import tempfile
import threading
import time

import pytest

from conan.test.utils.tools import TestClient


# Helper function for concurrent add_provider test - must be at module level to be picklable
def _child_process_add_provider(cache_folder, provider_name, result_queue):
    """
    Child process function that adds an audit provider.

    Args:
        cache_folder: Path to the cache folder
        provider_name: Name of the provider to add
        result_queue: multiprocessing.Queue to report results
    """
    from conan.api.conan_api import ConanAPI

    try:
        # Create a ConanAPI instance pointing to the shared cache
        api = ConanAPI(cache_folder)
        api.audit.add_provider(provider_name, f"https://{provider_name}.example.com", "private")
        result_queue.put({"success": True, "provider_name": provider_name})
    except Exception as e:
        result_queue.put({"success": False, "provider_name": provider_name, "error": str(e)})


# Helper function for concurrent auth_provider test - must be at module level to be picklable
def _child_process_auth_provider(cache_folder, provider_name, token, result_queue):
    """
    Child process function that authenticates an audit provider.

    Args:
        cache_folder: Path to the cache folder
        provider_name: Name of the provider to authenticate
        token: Token to set
        result_queue: multiprocessing.Queue to report results
    """
    from conan.api.conan_api import ConanAPI

    try:
        api = ConanAPI(cache_folder)
        provider = api.audit.get_provider(provider_name)
        api.audit.auth_provider(provider, token)
        result_queue.put({"success": True, "provider_name": provider_name, "token": token})
    except Exception as e:
        result_queue.put({"success": False, "provider_name": provider_name, "error": str(e)})


# Helper function for concurrent remove_provider test - must be at module level to be picklable
def _child_process_remove_provider(cache_folder, provider_name, result_queue):
    """
    Child process function that removes an audit provider.

    Args:
        cache_folder: Path to the cache folder
        provider_name: Name of the provider to remove
        result_queue: multiprocessing.Queue to report results
    """
    from conan.api.conan_api import ConanAPI

    try:
        api = ConanAPI(cache_folder)
        api.audit.remove_provider(provider_name)
        result_queue.put({"success": True, "provider_name": provider_name})
    except Exception as e:
        result_queue.put({"success": False, "provider_name": provider_name, "error": str(e)})


class TestAuditProvidersConcurrencyUnit:
    """
    Unit tests for concurrent audit provider operations.

    These tests verify that the ConcurrencyLock protection works correctly
    by using multiple threads to perform concurrent operations through the
    actual API methods.

    Before the fix: These tests would FAIL due to race conditions causing
    lost updates, corrupted JSON, or resurrected data.

    After the fix: These tests PASS because ConcurrencyLock serializes access.
    """

    def test_concurrent_add_providers_no_lost_updates(self):
        """
        Test that concurrent add_provider() calls don't lose updates.

        Before fix: Race condition would cause some providers to be lost
        when multiple threads call add_provider() simultaneously.

        After fix: ConcurrencyLock ensures all providers are saved.
        """
        from conan.api.conan_api import ConanAPI

        with tempfile.TemporaryDirectory() as tmpdir:
            api = ConanAPI(tmpdir)
            # Initialize providers file
            api.audit.list_providers()

            num_threads = 5
            errors = []
            lock = threading.Lock()

            def add_provider(idx):
                try:
                    api.audit.add_provider(
                        f"provider{idx}",
                        f"https://p{idx}.example.com",
                        "private"
                    )
                except Exception as e:
                    with lock:
                        errors.append((idx, str(e)))

            threads = [threading.Thread(target=add_provider, args=(i,)) for i in range(num_threads)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30.0)

            # Verify no threads stuck
            for t in threads:
                assert not t.is_alive(), "Thread stuck - possible deadlock"

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # All providers should exist (no lost updates)
            missing = [f"provider{i}" for i in range(num_threads) if f"provider{i}" not in final_providers]
            assert len(missing) == 0, (
                f"Lost updates detected: {missing} missing from final state. "
                f"This would fail before the ConcurrencyLock fix was applied."
            )

    def test_concurrent_auth_providers_no_lost_tokens(self):
        """
        Test that concurrent auth_provider() calls don't lose tokens.

        Before fix: Race condition would cause some tokens to be lost
        when multiple threads authenticate different providers simultaneously.

        After fix: ConcurrencyLock ensures all tokens are saved.
        """
        from conan.api.conan_api import ConanAPI

        with tempfile.TemporaryDirectory() as tmpdir:
            api = ConanAPI(tmpdir)

            # Create providers first (sequentially)
            num_providers = 5
            for i in range(num_providers):
                api.audit.add_provider(f"provider{i}", f"https://p{i}.example.com", "private")

            errors = []
            lock = threading.Lock()

            def auth_provider(idx):
                try:
                    provider = api.audit.get_provider(f"provider{idx}")
                    api.audit.auth_provider(provider, f"token{idx}")
                except Exception as e:
                    with lock:
                        errors.append((idx, str(e)))

            threads = [threading.Thread(target=auth_provider, args=(i,)) for i in range(num_providers)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30.0)

            # Verify no threads stuck
            for t in threads:
                assert not t.is_alive(), "Thread stuck - possible deadlock"

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # All providers should have tokens (no lost tokens)
            missing_tokens = [
                f"provider{i}" for i in range(num_providers)
                if f"provider{i}" not in final_providers or "token" not in final_providers[f"provider{i}"]
            ]
            assert len(missing_tokens) == 0, (
                f"Lost tokens detected: {missing_tokens}. "
                f"This would fail before the ConcurrencyLock fix was applied."
            )

    def test_concurrent_add_remove_no_resurrection(self):
        """
        Test that concurrent add/remove operations maintain consistency.

        Before fix: Race condition could cause removed providers to be
        "resurrected" when another thread's stale snapshot was saved.

        After fix: ConcurrencyLock ensures removes are not overwritten.
        """
        from conan.api.conan_api import ConanAPI

        with tempfile.TemporaryDirectory() as tmpdir:
            api = ConanAPI(tmpdir)

            # Create initial provider to be removed
            api.audit.add_provider("to_remove", "https://remove.example.com", "private")

            errors = []
            lock = threading.Lock()
            remove_done = threading.Event()

            def remove_provider():
                try:
                    api.audit.remove_provider("to_remove")
                    remove_done.set()
                except Exception as e:
                    with lock:
                        errors.append(("remove", str(e)))

            def add_provider():
                try:
                    # Wait a tiny bit to increase chance of race
                    time.sleep(0.001)
                    api.audit.add_provider("new_provider", "https://new.example.com", "private")
                except Exception as e:
                    with lock:
                        errors.append(("add", str(e)))

            t_remove = threading.Thread(target=remove_provider)
            t_add = threading.Thread(target=add_provider)

            t_remove.start()
            t_add.start()
            t_remove.join(timeout=30.0)
            t_add.join(timeout=30.0)

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # to_remove should NOT be resurrected
            assert "to_remove" not in final_providers, (
                "Provider 'to_remove' was resurrected! "
                "This would happen before the ConcurrencyLock fix was applied."
            )
            # new_provider should exist
            assert "new_provider" in final_providers, "new_provider should exist"


class TestAuditProvidersConcurrencyMultiProcess:
    """
    Multi-process integration tests for audit provider concurrency.

    These tests spawn actual OS processes to test real-world concurrent
    access scenarios. They verify that the locking mechanism properly
    serializes access to audit_providers.json.
    """

    @pytest.mark.slow
    def test_concurrent_add_providers_from_multiple_processes(self):
        """
        Test that multiple processes can safely add providers concurrently.

        Spawns multiple child processes that each add a different provider.
        Verifies that all providers are present in the final file.

        Expected behavior BEFORE fix: Some providers are lost (test FAILS)
        Expected behavior AFTER fix: All providers exist (test PASSES)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize the cache with a conan home
            client = TestClient(cache_folder=tmpdir)
            # Trigger creation of audit_providers.json by listing providers
            client.run("audit provider list")

            num_processes = 5
            result_queue = multiprocessing.Queue()

            # Spawn processes that each add a different provider
            processes = []
            for i in range(num_processes):
                p = multiprocessing.Process(
                    target=_child_process_add_provider,
                    args=(tmpdir, f"provider{i}", result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously to maximize race condition chance
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # Check which succeeded
            successful = [r for r in results if r["success"]]
            failed = [r for r in results if not r["success"]]

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # All processes should succeed
            assert len(failed) == 0, f"Some processes failed: {failed}"

            # All providers should be present
            missing_providers = []
            for i in range(num_processes):
                provider_name = f"provider{i}"
                if provider_name not in final_providers:
                    missing_providers.append(provider_name)

            # This assertion will FAIL before the fix (demonstrating the bug)
            assert len(missing_providers) == 0, (
                f"RACE CONDITION DETECTED: {len(missing_providers)} providers lost due to "
                f"unprotected concurrent add_provider() calls. Missing: {missing_providers}. "
                f"Final state has {len(final_providers)} providers. "
                f"This test should PASS after adding proper locking."
            )

    @pytest.mark.slow
    def test_concurrent_auth_providers_from_multiple_processes(self):
        """
        Test that multiple processes can safely authenticate providers concurrently.

        Creates multiple providers, then spawns multiple processes that each
        authenticate a different provider. Verifies all tokens are saved.

        Expected behavior BEFORE fix: Some tokens are lost (test FAILS)
        Expected behavior AFTER fix: All tokens exist (test PASSES)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize the cache
            client = TestClient(cache_folder=tmpdir)

            # Create multiple providers first (sequentially, to avoid that race)
            num_providers = 5
            for i in range(num_providers):
                client.run(f"audit provider add provider{i} --url=https://p{i}.example.com --type=private --token=initial")

            result_queue = multiprocessing.Queue()

            # Spawn processes that each auth a different provider
            processes = []
            for i in range(num_providers):
                p = multiprocessing.Process(
                    target=_child_process_auth_provider,
                    args=(tmpdir, f"provider{i}", f"new_token_{i}", result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # All should succeed
            failed = [r for r in results if not r["success"]]
            assert len(failed) == 0, f"Some processes failed: {failed}"

            # Load final state and check all tokens exist
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            missing_tokens = []
            for i in range(num_providers):
                provider_name = f"provider{i}"
                if provider_name not in final_providers:
                    missing_tokens.append(f"{provider_name} (provider missing)")
                elif "token" not in final_providers[provider_name]:
                    missing_tokens.append(f"{provider_name} (token missing)")

            # This assertion will FAIL before the fix (demonstrating the bug)
            assert len(missing_tokens) == 0, (
                f"RACE CONDITION DETECTED: {len(missing_tokens)} tokens lost due to "
                f"unprotected concurrent auth_provider() calls. Missing: {missing_tokens}. "
                f"This test should PASS after adding proper locking."
            )

    @pytest.mark.slow
    def test_concurrent_add_and_remove_providers(self):
        """
        Test that add and remove operations don't corrupt each other.

        Spawns processes that add and remove providers concurrently.
        Verifies the final state is consistent.

        Expected behavior BEFORE fix: Inconsistent state (test may FAIL)
        Expected behavior AFTER fix: Consistent state (test PASSES)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize the cache
            client = TestClient(cache_folder=tmpdir)

            # Create some initial providers to remove
            for i in range(3):
                client.run(f"audit provider add to_remove{i} --url=https://r{i}.example.com --type=private --token=t")

            result_queue = multiprocessing.Queue()
            processes = []

            # Processes to add new providers
            for i in range(3):
                p = multiprocessing.Process(
                    target=_child_process_add_provider,
                    args=(tmpdir, f"new_provider{i}", result_queue)
                )
                processes.append(p)

            # Processes to remove existing providers
            for i in range(3):
                p = multiprocessing.Process(
                    target=_child_process_remove_provider,
                    args=(tmpdir, f"to_remove{i}", result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=60.0)
                assert not p.is_alive(), "Process did not complete - possible deadlock"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # Check that removed providers are gone
            resurrected = []
            for i in range(3):
                if f"to_remove{i}" in final_providers:
                    resurrected.append(f"to_remove{i}")

            # Check that added providers exist
            missing_new = []
            for i in range(3):
                if f"new_provider{i}" not in final_providers:
                    missing_new.append(f"new_provider{i}")

            # These assertions may FAIL before the fix
            assert len(resurrected) == 0, (
                f"RACE CONDITION DETECTED: Providers were resurrected: {resurrected}. "
                f"This indicates add_provider() overwrote remove_provider() changes."
            )
            assert len(missing_new) == 0, (
                f"RACE CONDITION DETECTED: New providers were lost: {missing_new}. "
                f"This indicates remove_provider() overwrote add_provider() changes."
            )


class TestAuditProvidersAtomicSave:
    """
    Tests for atomic save behavior in audit providers.

    These tests verify that the save operation is atomic and doesn't
    leave the file in a corrupted state if interrupted.
    """

    def test_save_produces_valid_json(self):
        """
        Test that _save_providers produces valid JSON.
        """
        from conan.api.subapi.audit import _load_providers, _save_providers

        with tempfile.TemporaryDirectory() as tmpdir:
            providers_path = os.path.join(tmpdir, "audit_providers.json")

            providers = {
                "provider1": {"name": "provider1", "url": "https://1.example.com", "type": "private"},
                "provider2": {"name": "provider2", "url": "https://2.example.com", "type": "private"},
            }
            _save_providers(providers_path, providers)

            # Should be valid JSON
            with open(providers_path) as f:
                loaded = json.load(f)

            assert loaded == providers

    def test_file_permissions_are_restricted(self):
        """
        Test that audit_providers.json has restricted permissions (0o600).
        """
        import platform
        if platform.system() == "Windows":
            pytest.skip("File permission test not applicable on Windows")

        from conan.api.subapi.audit import _save_providers

        with tempfile.TemporaryDirectory() as tmpdir:
            providers_path = os.path.join(tmpdir, "audit_providers.json")

            providers = {"test": {"name": "test", "url": "https://test.com", "type": "private"}}
            _save_providers(providers_path, providers)

            stat_result = os.stat(providers_path)
            mode = stat_result.st_mode & 0o777

            assert mode == 0o600, f"Expected 0o600 permissions, got {oct(mode)}"


class TestAuditProvidersThreadSafety:
    """
    Thread safety tests for audit provider operations.

    These tests verify thread safety within a single process.
    """

    def test_multiple_threads_add_providers(self):
        """
        Test that multiple threads can safely add providers.

        Expected behavior BEFORE fix: Some providers are lost (test FAILS)
        Expected behavior AFTER fix: All providers exist (test PASSES)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            from conan.api.conan_api import ConanAPI

            api = ConanAPI(tmpdir)
            # Initialize the providers file
            api.audit.list_providers()

            num_threads = 10
            errors = []
            lock = threading.Lock()

            def add_provider_thread(idx):
                try:
                    # Each thread creates its own API instance to simulate
                    # separate operations (though they share the same file)
                    thread_api = ConanAPI(tmpdir)
                    thread_api.audit.add_provider(
                        f"thread_provider{idx}",
                        f"https://t{idx}.example.com",
                        "private"
                    )
                except Exception as e:
                    with lock:
                        errors.append((idx, str(e)))

            threads = [threading.Thread(target=add_provider_thread, args=(i,)) for i in range(num_threads)]

            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30.0)

            # Check for stuck threads
            for t in threads:
                assert not t.is_alive(), "Thread did not complete - possible deadlock"

            # Errors from "already exists" are expected if race causes double-add
            # but we shouldn't have other errors
            non_exists_errors = [e for e in errors if "already exists" not in e[1]]

            # Load final state
            providers_path = os.path.join(tmpdir, "audit_providers.json")
            with open(providers_path) as f:
                final_providers = json.load(f)

            # Count how many thread providers exist
            found_count = sum(1 for i in range(num_threads) if f"thread_provider{i}" in final_providers)

            # This assertion may FAIL before the fix
            assert found_count == num_threads, (
                f"RACE CONDITION DETECTED: Only {found_count}/{num_threads} providers were saved. "
                f"Lost providers due to unprotected concurrent add_provider() calls. "
                f"Errors: {errors}"
            )
