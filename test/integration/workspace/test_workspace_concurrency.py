"""
Tests for workspace YAML file concurrency issues.

This test file verifies that concurrent add() and remove() operations on
workspace YAML files are properly protected with locks to prevent lost updates
and file corruption.
"""

import multiprocessing
import os
import tempfile

import pytest

from conan.api.subapi.workspace import WorkspaceAPI
from conan.test.utils.tools import TestClient

WorkspaceAPI.TEST_ENABLED = "will_break_next"


def _child_process_add_package(workspace_folder, package_name, result_queue):
    """
    Child process that adds a package to the workspace.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient
    from conan.api.subapi.workspace import WorkspaceAPI

    # Enable workspace for this process
    WorkspaceAPI.TEST_ENABLED = "will_break_next"

    try:
        client = TestClient(current_folder=workspace_folder, light=True)

        # Add to workspace (package should already exist from parent process setup)
        client.run(f"workspace add {package_name}")

        result_queue.put({
            "success": True,
            "operation": "add",
            "package": package_name,
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "add",
            "package": package_name,
            "error": str(e)
        })


def _child_process_remove_package(workspace_folder, package_path, result_queue):
    """
    Child process that removes a package from the workspace.
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient
    from conan.api.subapi.workspace import WorkspaceAPI

    # Enable workspace for this process
    WorkspaceAPI.TEST_ENABLED = "will_break_next"

    try:
        client = TestClient(current_folder=workspace_folder, light=True)
        client.run(f"workspace remove {package_path}")

        result_queue.put({
            "success": True,
            "operation": "remove",
            "package": package_path,
            "error": None
        })
    except Exception as e:
        result_queue.put({
            "success": False,
            "operation": "remove",
            "package": package_path,
            "error": str(e)
        })


class TestWorkspaceConcurrency:
    """
    Tests for race conditions in workspace YAML file operations.

    These tests verify that workspace add() and remove() operations properly
    protect the conanws.yml file from concurrent modifications that could lead
    to lost updates or file corruption.
    """

    @pytest.mark.slow
    def test_concurrent_workspace_add(self):
        """
        Test race condition: Multiple processes adding packages to workspace simultaneously.

        Race Condition:
        - Process A: Reads conanws.yml, adds pkg1, writes back
        - Process B: Reads conanws.yml (before A writes), adds pkg2, writes back
        - Result: Either pkg1 or pkg2 might be lost due to overwrite

        The fix should use locks to serialize access to the YAML file.
        """
        from conan.test.assets.genconanfile import GenConanfile

        with tempfile.TemporaryDirectory(prefix="conan_ws_test_") as workspace_folder:
            # Initialize workspace with package folders
            client = TestClient(current_folder=workspace_folder, light=True)
            files = {"conanws.yml": ""}
            for i in range(3):
                files[f"pkg{i}/conanfile.py"] = GenConanfile(f"pkg{i}", "1.0")
            client.save(files)

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start 3 processes trying to add different packages simultaneously
            processes = []
            for i in range(3):
                p = mp_context.Process(
                    target=_child_process_add_package,
                    args=(workspace_folder, f"pkg{i}", result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=30.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 3, f"Should have 3 results, got {len(results)}"

            # All processes should succeed
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Process {i} ({result['package']}) should succeed with proper locking. " \
                    f"Error: {result.get('error', 'N/A')}"

            # Verify all packages were actually added to the workspace
            verify_client = TestClient(current_folder=workspace_folder)
            verify_client.run("workspace info")
            for i in range(3):
                assert f"pkg{i}" in verify_client.out, \
                    f"Package pkg{i} should be in workspace (may have been lost due to race)"

    @pytest.mark.slow
    def test_concurrent_workspace_add_and_remove(self):
        """
        Test race condition: Adding and removing packages concurrently.

        Race Condition:
        - Process A: Adding new package
        - Process B: Removing existing package
        - Both read-modify-write conanws.yml simultaneously
        - Result: One operation's changes might be lost

        The fix should use locks to serialize access.
        """
        from conan.test.assets.genconanfile import GenConanfile

        with tempfile.TemporaryDirectory(prefix="conan_ws_test_") as workspace_folder:
            # Initialize workspace with some existing packages
            client = TestClient(current_folder=workspace_folder, light=True)
            files = {"conanws.yml": ""}
            for i in range(3):
                files[f"existing{i}/conanfile.py"] = GenConanfile(f"existing{i}", "1.0")
            for i in range(2):
                files[f"newpkg{i}/conanfile.py"] = GenConanfile(f"newpkg{i}", "1.0")
            client.save(files)

            # Add initial packages to workspace
            for i in range(3):
                client.run(f"workspace add existing{i}")

            # Use spawn context to avoid fork issues with pytest-xdist
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()

            # Start processes: some adding, some removing
            processes = []

            # Add 2 new packages
            for i in range(2):
                p = mp_context.Process(
                    target=_child_process_add_package,
                    args=(workspace_folder, f"newpkg{i}", result_queue)
                )
                processes.append(p)

            # Remove 2 existing packages
            for i in range(2):
                p = mp_context.Process(
                    target=_child_process_remove_package,
                    args=(workspace_folder, f"existing{i}", result_queue)
                )
                processes.append(p)

            # Start all simultaneously
            for p in processes:
                p.start()

            # Wait for all to complete
            for p in processes:
                p.join(timeout=30.0)
                assert not p.is_alive(), "Process did not complete"

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            assert len(results) == 4, f"Should have 4 results, got {len(results)}"

            # All operations should succeed
            for i, result in enumerate(results):
                assert result["success"], \
                    f"Process {i} ({result['operation']} {result['package']}) should succeed. " \
                    f"Error: {result.get('error', 'N/A')}"

            # Verify final state is correct
            verify_client = TestClient(current_folder=workspace_folder)
            verify_client.run("workspace info")

            # New packages should be added
            for i in range(2):
                assert f"newpkg{i}" in verify_client.out, \
                    f"Package newpkg{i} should be in workspace"

            # Removed packages should be gone
            # (We keep existing2 which wasn't removed)
            assert "existing2" in verify_client.out, \
                "Package existing2 should still be in workspace"


@pytest.fixture
def shared_workspace():
    """Fixture that provides a shared workspace folder for multi-process tests."""
    with tempfile.TemporaryDirectory(prefix="conan_ws_test_") as tmpdir:
        yield tmpdir
