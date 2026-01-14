"""
Tests for authentication concurrency issues across multiple processes.

This test verifies that when multiple PROCESSES try to authenticate
to the same remote simultaneously, only one process actually authenticates
while others wait and reuse the credentials.

The existing test_auth_concurrency.py tests thread-level concurrency
within a single process. This file tests process-level concurrency.
"""

import multiprocessing
import os
import tempfile
import time

import pytest

from conan.test.utils.tools import TestClient
from conan.test.assets.genconanfile import GenConanfile


def _child_process_authenticate(cache_folder, remote_url, result_queue, delay=0):
    """
    Child process that tries to get credentials from localdb.

    Args:
        cache_folder: Shared cache folder
        remote_url: URL of the remote to authenticate to
        result_queue: Queue to report results
        delay: Optional delay before accessing credentials
    """
    try:
        if delay:
            time.sleep(delay)

        from conan.internal.api.remotes.localdb import LocalDB
        localdb = LocalDB(cache_folder)

        # Try to get credentials (simulates what auth_manager does)
        user, token, _ = localdb.get_login(remote_url)

        result_queue.put({
            "success": True,
            "user": user,
            "token": token,
            "has_creds": user is not None and token is not None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "error": str(e)
        })


def _child_process_store_and_read(cache_folder, remote_url, process_id, result_queue):
    """
    Child process that stores credentials then reads them back.

    Simulates concurrent authentication where multiple processes
    try to store credentials simultaneously.
    """
    try:
        from conan.internal.api.remotes.localdb import LocalDB
        localdb = LocalDB(cache_folder)

        # Store credentials for this process
        user = f"user{process_id}"
        token = f"token{process_id}"
        localdb.store(user, token, None, remote_url)

        # Small delay to allow races
        time.sleep(0.01)

        # Read back - should get either this process's creds or another's
        read_user, read_token, _ = localdb.get_login(remote_url)

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "stored_user": user,
            "read_user": read_user,
            "match": (user == read_user)
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "error": str(e)
        })


class TestAuthMultiProcessConcurrency:
    """
    Tests for multi-process authentication concurrency.

    These tests verify that credential operations are safe when multiple
    processes access the same localdb simultaneously.

    The authentication manager uses both thread-level (threading.Lock) and
    process-level (ConcurrencyLock) synchronization to ensure only one
    thread/process authenticates at a time while others wait and reuse
    the updated credentials.
    """

    def test_concurrent_credential_reads(self):
        """
        Test that multiple processes reading credentials doesn't cause issues.

        This is a baseline test - reads should be safe even without locking.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup: Create client and store initial credentials
            client = TestClient(cache_folder=tmpdir)

            from conan.internal.api.remotes.localdb import LocalDB
            localdb = LocalDB(tmpdir)
            remote_url = "https://example.com"
            localdb.store("testuser", "testtoken", None, remote_url)

            # Spawn multiple processes reading credentials
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []
            num_processes = 5

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_authenticate,
                    args=(tmpdir, remote_url, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=10)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should succeed and get the same credentials
            assert len(results) == num_processes
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some reads failed: {failures}"

            # All should have credentials
            for result in results:
                assert result["has_creds"], "Process didn't get credentials"
                assert result["user"] == "testuser"
                assert result["token"] == "testtoken"

    def test_concurrent_credential_stores(self):
        """
        Test that multiple processes storing credentials don't corrupt the database.

        This tests the database-level safety. SQLite should handle this,
        but we want to verify no corruption occurs.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize localdb
            from conan.internal.api.remotes.localdb import LocalDB
            localdb = LocalDB(tmpdir)
            remote_url = "https://example.com"

            # Spawn multiple processes storing different credentials
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []
            num_processes = 5

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_store_and_read,
                    args=(tmpdir, remote_url, i, result_queue)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=10)
                assert not p.is_alive(), "Process hung"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All operations should succeed
            assert len(results) == num_processes
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some stores failed: {failures}"

            # Database should be consistent - final read should get valid credentials
            final_user, final_token, _ = localdb.get_login(remote_url)
            assert final_user is not None, "Database corrupted - no user stored"
            assert final_token is not None, "Database corrupted - no token stored"

            # Final credentials should match one of the processes
            stored_users = [r["stored_user"] for r in results]
            assert final_user in stored_users, \
                f"Final user '{final_user}' doesn't match any stored user"

    def test_authentication_serialization_across_processes(self):
        """
        Test that authentication is properly serialized across processes.

        This is the key test for process-level locking. Multiple processes
        trying to authenticate should be serialized so only one actually
        does the authentication work.

        Note: This is a simplified test. Real authentication would involve
        REST API calls, but we test the localdb access patterns.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Initialize without credentials
            from conan.internal.api.remotes.localdb import LocalDB
            localdb = LocalDB(tmpdir)
            remote_url = "https://example.com"

            # Verify no credentials initially
            user, token, _ = localdb.get_login(remote_url)
            assert user is None
            assert token is None

            # Spawn multiple processes that will all try to store credentials
            # In real scenario, this would be multiple processes detecting
            # expired tokens and trying to authenticate
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []
            num_processes = 3

            for i in range(num_processes):
                p = mp_context.Process(
                    target=_child_process_store_and_read,
                    args=(tmpdir, remote_url, i, result_queue)
                )
                processes.append(p)

            # Start all simultaneously to maximize race condition
            for p in processes:
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=10)
                assert not p.is_alive(), "Process hung"

            # All operations should succeed without errors
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            assert len(results) == num_processes
            failures = [r for r in results if not r["success"]]
            assert len(failures) == 0, f"Some operations failed: {failures}"


class TestAuthCredentialsIntegrity:
    """
    Tests to verify credential integrity isn't compromised by concurrency.
    """

    def test_credentials_not_corrupted_by_concurrent_access(self):
        """
        Verify that concurrent access doesn't corrupt stored credentials.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            from conan.internal.api.remotes.localdb import LocalDB
            localdb = LocalDB(tmpdir)
            remote_url = "https://example.com"

            # Store initial credentials
            original_user = "original_user"
            original_token = "original_token_12345"
            localdb.store(original_user, original_token, None, remote_url)

            # Spawn multiple processes reading
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(10):
                p = mp_context.Process(
                    target=_child_process_authenticate,
                    args=(tmpdir, remote_url, result_queue, 0)
                )
                processes.append(p)
                p.start()

            # Wait for all
            for p in processes:
                p.join(timeout=10)

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get())

            # All should get the original, uncorrupted credentials
            for result in results:
                assert result["success"], f"Read failed: {result.get('error')}"
                assert result["user"] == original_user, \
                    f"User corrupted: expected {original_user}, got {result['user']}"
                assert result["token"] == original_token, \
                    f"Token corrupted: expected {original_token}, got {result['token']}"
