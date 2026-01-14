"""
Utilities for multi-process concurrency testing.

This module provides tools to spawn multiple Conan processes accessing
a shared cache simultaneously, enabling tests for race conditions and
concurrent access safety.
"""

import os
import subprocess
import sys
import tempfile
import multiprocessing
import time
import socket
from concurrent.futures import ProcessPoolExecutor, as_completed
from contextlib import contextmanager

from conan.test.utils.server_launcher import TestServerLauncher
from conan.internal import REVISIONS


class MultiProcessTestClient:
    """
    A test client that runs Conan commands as separate OS processes
    with a shared cache folder, enabling true multi-process concurrency testing.

    Unlike the regular TestClient which runs Conan in-process, this client
    spawns actual `conan` CLI subprocesses that compete for cache resources.

    Uses `python -m conan` to ensure subprocesses use the same Python environment
    and local development code as the test runner.
    """

    def __init__(self, shared_cache_folder):
        """
        Initialize a multi-process test client.

        Args:
            shared_cache_folder: Path to the shared Conan cache folder.
                All processes will use this as CONAN_HOME.
        """
        self.cache = shared_cache_folder
        self._python_executable = sys.executable

        # Calculate conan source directory in parent process where conan is available
        import conan
        self._conan_source_dir = os.path.dirname(os.path.dirname(conan.__file__))

    def run_conan(self, args, cwd=None, timeout=300):
        """
        Run a conan command as a subprocess with the shared cache.

        Args:
            args: List of command arguments (e.g., ["create", ".", "--name=pkg"])
            cwd: Working directory for the command
            timeout: Timeout in seconds (default 5 minutes)

        Returns:
            subprocess.CompletedProcess with returncode, stdout, stderr
        """
        env = os.environ.copy()
        env["CONAN_HOME"] = self.cache

        # Ensure subprocess uses the same conan module as the test runner
        # by adding the conan source directory to PYTHONPATH
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{self._conan_source_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = self._conan_source_dir

        # Run as "python -m conans.conan" to use the same Python environment and
        # local development code as the test runner
        cmd = [self._python_executable, "-m", "conans.conan"] + args

        try:
            result = subprocess.run(
                cmd,
                env=env,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            return result
        except subprocess.TimeoutExpired as e:
            # Return a fake CompletedProcess with timeout info
            class TimeoutResult:
                returncode = -1
                stdout = e.stdout or ""
                stderr = f"Command timed out after {timeout}s"
            return TimeoutResult()

    def run_concurrent(self, commands, max_workers=None, timeout=300):
        """
        Run multiple conan commands concurrently in separate processes.

        Args:
            commands: List of (args, cwd) tuples or just args lists.
                Each args is a list of command arguments.
            max_workers: Maximum concurrent processes (default: number of commands)
            timeout: Timeout per command in seconds

        Returns:
            List of subprocess.CompletedProcess results in the same order
            as the input commands.
        """
        if max_workers is None:
            max_workers = len(commands)

        # Normalize commands to (args, cwd) tuples
        normalized = []
        for cmd in commands:
            if isinstance(cmd, tuple):
                normalized.append(cmd)
            else:
                normalized.append((cmd, None))

        results = [None] * len(normalized)

        # Use multiprocessing context to avoid fork issues in pytest
        mp_context = multiprocessing.get_context('spawn')
        with ProcessPoolExecutor(max_workers=max_workers, mp_context=mp_context) as executor:
            # Submit all tasks and track their indices
            future_to_idx = {
                executor.submit(_run_conan_worker,
                               self._python_executable,
                               self.cache,
                               self._conan_source_dir,
                               args,
                               cwd,
                               timeout): idx
                for idx, (args, cwd) in enumerate(normalized)
            }

            # Collect results
            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    class ErrorResult:
                        returncode = -1
                        stdout = ""
                        stderr = str(e)
                    results[idx] = ErrorResult()

        return results


def _run_conan_worker(python_executable, cache_folder, conan_source_dir, args, cwd, timeout):
    """
    Worker function for ProcessPoolExecutor.
    Must be a top-level function to be picklable.

    Uses "python -m conans.conan" to ensure the subprocess uses the same Python
    environment and local development code as the test runner.
    """
    env = os.environ.copy()
    env["CONAN_HOME"] = cache_folder

    # Ensure subprocess uses the same conan module as the test runner
    if "PYTHONPATH" in env:
        env["PYTHONPATH"] = f"{conan_source_dir}{os.pathsep}{env['PYTHONPATH']}"
    else:
        env["PYTHONPATH"] = conan_source_dir

    cmd = [python_executable, "-m", "conans.conan"] + args

    result = subprocess.run(
        cmd,
        env=env,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout
    )
    return result


def _find_available_port():
    """Find an available port on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


class RealTestServer:
    """
    A real HTTP test server that can be accessed from multiple processes.

    Unlike TestServer which uses fake URLs and in-process mocking, this
    class starts an actual HTTP server on localhost that subprocesses can connect to.
    """

    def __init__(self, read_permissions=None, write_permissions=None, users=None,
                 server_capabilities=None, base_path=None):
        """
        Initialize and start a real HTTP server for testing.

        Args:
            read_permissions: List of (package_pattern, users) tuples for read access
            write_permissions: List of (package_pattern, users) tuples for write access
            users: Dict of {username: password}
            server_capabilities: List of server capabilities
            base_path: Base directory for server storage
        """
        if read_permissions is None:
            read_permissions = [("*/*@*/*", "*")]
        if write_permissions is None:
            write_permissions = [("*/*@*/*", "*")]
        if users is None:
            users = {"admin": "password"}
        if server_capabilities is None:
            server_capabilities = [REVISIONS]
        elif REVISIONS not in server_capabilities:
            server_capabilities = list(server_capabilities) + [REVISIONS]

        self._base_path = base_path or tempfile.mkdtemp(prefix="conan_server_")

        # Find an available port dynamically to avoid conflicts
        port = _find_available_port()

        # Set the port via environment variable so TestServerLauncher uses it
        old_port_env = os.environ.get("CONAN_SERVER_PORT")
        os.environ["CONAN_SERVER_PORT"] = str(port)

        try:
            self._launcher = TestServerLauncher(
                base_path=self._base_path,
                read_permissions=read_permissions,
                write_permissions=write_permissions,
                users=users,
                base_url="v1",
                server_capabilities=server_capabilities
            )
        finally:
            # Restore original environment variable
            if old_port_env is not None:
                os.environ["CONAN_SERVER_PORT"] = old_port_env
            else:
                os.environ.pop("CONAN_SERVER_PORT", None)

        # Start the server
        self._launcher.start(daemon=True)
        time.sleep(0.5)  # Give server time to start

        # The real URL that subprocesses can connect to
        self.url = f"http://localhost:{self._launcher.port}"

    @property
    def server_store(self):
        """Access to the server's storage for direct manipulation in tests."""
        return self._launcher.server_store

    def stop(self):
        """Stop the server and clean up."""
        self._launcher.stop()
        # Clean up the base path if it was auto-created
        if self._base_path.startswith(tempfile.gettempdir()):
            import shutil
            try:
                shutil.rmtree(self._base_path, ignore_errors=True)
            except Exception:
                pass  # Best effort cleanup

    def __str__(self):
        """Return the server URL for serialization."""
        return self.url

    def __repr__(self):
        """Return a representation of the server."""
        return f"RealTestServer @ {self.url}"

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()


@contextmanager
def shared_cache():
    """
    Context manager that creates a temporary shared cache folder.

    Usage:
        with shared_cache() as cache_folder:
            client = MultiProcessTestClient(cache_folder)
            # ... run concurrent tests
    """
    with tempfile.TemporaryDirectory(prefix="conan_test_cache_") as tmpdir:
        yield tmpdir


def run_parallel_exports(client, conanfile_content, name, version, count=5):
    """
    Helper to run multiple exports of the same package concurrently.

    Args:
        client: MultiProcessTestClient instance
        conanfile_content: Content of the conanfile.py
        name: Package name
        version: Package version
        count: Number of concurrent exports

    Returns:
        List of results from concurrent exports
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        conanfile_path = os.path.join(tmpdir, "conanfile.py")
        with open(conanfile_path, "w") as f:
            f.write(conanfile_content)

        commands = [
            (["export", ".", f"--name={name}", f"--version={version}"], tmpdir)
            for _ in range(count)
        ]

        return client.run_concurrent(commands)


def run_parallel_creates(client, conanfile_content, name, version, count=5):
    """
    Helper to run multiple creates of the same package concurrently.

    Args:
        client: MultiProcessTestClient instance
        conanfile_content: Content of the conanfile.py
        name: Package name
        version: Package version
        count: Number of concurrent creates

    Returns:
        List of results from concurrent creates
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        conanfile_path = os.path.join(tmpdir, "conanfile.py")
        with open(conanfile_path, "w") as f:
            f.write(conanfile_content)

        commands = [
            (["create", ".", f"--name={name}", f"--version={version}"], tmpdir)
            for _ in range(count)
        ]

        return client.run_concurrent(commands)
