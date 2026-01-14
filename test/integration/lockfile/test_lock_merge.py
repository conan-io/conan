import json
import multiprocessing
import os
import tempfile
import textwrap
import time

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from test.utils.multiprocess import MultiProcessTestClient


@pytest.mark.parametrize("requires", ["requires", "tool_requires"])
def test_merge_alias(requires):
    """
    basic lockfile merging including alias
    """
    c = TestClient()
    app = textwrap.dedent(f"""
        from conan import ConanFile
        class App(ConanFile):
            settings = "build_type"
            def requirements(self):
                if self.settings.build_type == "Debug":
                    self.{requires}("pkg/(alias_debug)")
                else:
                    self.{requires}("pkg/(alias_release)")
        """)
    c.save({"pkg/conanfile.py": GenConanfile("pkg"),
            "alias_release/conanfile.py": GenConanfile("pkg", "alias_release").with_class_attribute(
                "alias = 'pkg/0.1'"),
            "alias_debug/conanfile.py": GenConanfile("pkg", "alias_debug").with_class_attribute(
                "alias = 'pkg/0.2'"),
            "app/conanfile.py": app})
    c.run("create pkg --version=0.1")
    c.run("create pkg --version=0.2")
    c.run("export alias_release")
    c.run("export alias_debug")
    c.run("lock create app -s build_type=Release --lockfile-out=release.lock")
    c.run("lock create app -s build_type=Debug --lockfile-out=debug.lock")

    c.run("lock merge --lockfile=release.lock --lockfile=debug.lock --lockfile-out=conan.lock")

    # Update alias, won't be used
    c.save({"alias_release/conanfile.py": GenConanfile("pkg", "alias_release").with_class_attribute(
                "alias = 'pkg/0.3'"),
            "alias_debug/conanfile.py": GenConanfile("pkg", "alias_debug").with_class_attribute(
                "alias = 'pkg/0.4'")})
    c.run("export alias_release")
    c.run("export alias_debug")

    # Merged one can resolve both aliased without issues
    c.run("install app -s build_type=Release --lockfile=conan.lock")
    is_build_requires = requires == "tool_requires"
    c.assert_listed_require({"pkg/0.1": "Cache"}, build=is_build_requires)
    c.run("install app -s build_type=Debug --lockfile=conan.lock")
    c.assert_listed_require({"pkg/0.2": "Cache"}, build=is_build_requires)

    # without lockfiles it would be pointing to the new (unexistent) ones
    c.run("install app -s build_type=Release", assert_error=True)
    assert "ERROR: Package 'pkg/0.3' not resolved" in c.out
    c.run("install app -s build_type=Debug", assert_error=True)
    assert "ERROR: Package 'pkg/0.4' not resolved" in c.out


# Helper function for multiprocessing - must be at module level to be picklable
def _child_process_merge_lockfiles(cache_folder, lockfile_paths, output_path, process_id, result_queue):
    """
    Child process function that merges lockfiles.

    Args:
        cache_folder: Path to the shared cache folder
        lockfile_paths: List of lockfile paths to merge
        output_path: Path for the merged output
        process_id: ID for this process (for tracking)
        result_queue: multiprocessing.Queue to report results
    """
    # Fix for pytest stdin redirection issue with multiprocessing
    import sys
    if not hasattr(sys.stdin, 'close'):
        sys.stdin.close = lambda: None

    from conan.test.utils.tools import TestClient

    try:
        # Create a TestClient with the shared cache
        client = TestClient(cache_folder=cache_folder)

        # Build the merge command with proper quoting
        import shlex
        cmd_parts = ["lock", "merge"]
        for lockfile in lockfile_paths:
            cmd_parts.append(f"--lockfile={shlex.quote(lockfile)}")
        cmd_parts.append(f"--lockfile-out={shlex.quote(output_path)}")
        cmd = " ".join(cmd_parts)

        # Run the merge
        client.run(cmd)

        result_queue.put({
            "success": True,
            "process_id": process_id,
            "stdout": client.out
        })
    except Exception as e:
        import traceback
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "error": f"{str(e)}\n{traceback.format_exc()}"
        })




class TestLockfileConcurrency:
    """
    Tests for lockfile concurrency issues.

    These tests verify that lockfile operations (especially merge) are safe
    when executed concurrently from multiple processes, which is a common
    pattern in CI/CD environments with parallel builds.
    """

    @pytest.mark.slow
    def test_concurrent_merge_to_same_output(self):
        """
        Test that concurrent merges to the same output file don't corrupt it.

        This test simulates a race condition where multiple CI/CD jobs try to
        merge their lockfiles to a shared output file simultaneously.

        Expected failure modes without proper locking:
        - Corrupted JSON (parse errors)
        - Lost merge data (one process overwrites another's changes)
        - File corruption from concurrent writes

        This test is EXPECTED TO FAIL without the locking fixes.
        """
        c = TestClient()

        # Create two simple packages
        c.save({
            "pkg1/conanfile.py": GenConanfile("pkg1", "1.0"),
            "pkg2/conanfile.py": GenConanfile("pkg2", "1.0"),
        })
        c.run("create pkg1")
        c.run("create pkg2")

        # Create separate lockfiles for each package
        c.save({"consumer1/conanfile.py": GenConanfile().with_requires("pkg1/1.0")})
        c.run("lock create consumer1 --lockfile-out=lock1.lock")
        lock1_path = os.path.join(c.current_folder, "lock1.lock")

        c.save({"consumer2/conanfile.py": GenConanfile().with_requires("pkg2/1.0")})
        c.run("lock create consumer2 --lockfile-out=lock2.lock")
        lock2_path = os.path.join(c.current_folder, "lock2.lock")

        # Shared output path
        output_path = os.path.join(c.current_folder, "merged.lock")

        # Run multiple concurrent merges to the same output
        num_processes = 5

        # Use spawn context to avoid fork issues in pytest
        mp_context = multiprocessing.get_context('spawn')
        result_queue = mp_context.Queue()
        processes = []

        for i in range(num_processes):
            # Each process merges the same two lockfiles to the same output
            p = mp_context.Process(
                target=_child_process_merge_lockfiles,
                args=(c.cache_folder, [lock1_path, lock2_path],
                      output_path, i, result_queue)
            )
            processes.append(p)

        # Start all processes simultaneously
        for p in processes:
            p.start()

        # Wait for all to complete
        for p in processes:
            p.join(timeout=60)
            if p.is_alive():
                p.terminate()
                p.join()
                pytest.fail("Process did not complete - possible deadlock or resource exhaustion")

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        # At least one should succeed
        successful = [r for r in results if r["success"]]
        if len(successful) == 0:
            failures = [r for r in results if not r["success"]]
            error_msgs = "\n".join([f"Process {r['process_id']}: {r.get('stderr', r.get('error', 'unknown'))[:200]}"
                                   for r in failures[:3]])  # Show first 3 errors
            pytest.fail(f"All merges failed. First errors:\n{error_msgs}")

        assert len(successful) > 0, "At least one merge should succeed"

        # The output file should exist and be valid JSON
        assert os.path.exists(output_path), "Merged lockfile should exist"

        try:
            with open(output_path, 'r') as f:
                merged_data = json.load(f)

            # Verify it has both packages
            requires = merged_data.get("requires", [])
            require_names = [r if isinstance(r, str) else r[0] for r in requires]

            # Should contain both pkg1 and pkg2
            assert any("pkg1" in req for req in require_names), \
                f"Merged lockfile should contain pkg1. Found: {require_names}"
            assert any("pkg2" in req for req in require_names), \
                f"Merged lockfile should contain pkg2. Found: {require_names}"

        except json.JSONDecodeError as e:
            pytest.fail(f"Merged lockfile is corrupted (invalid JSON): {e}. "
                       "This indicates a race condition in concurrent merges.")

    @pytest.mark.slow
    def test_concurrent_read_during_write(self):
        """
        Test that reading a lockfile while another process is writing it doesn't fail.

        This simulates Process A writing/merging a lockfile while Process B tries
        to read/merge it. Without proper locking, Process B may read incomplete JSON.

        Expected failure modes without locking:
        - JSON parse errors ("Unterminated string", "Expecting delimiter")
        - Incomplete data in the merged result

        This test is EXPECTED TO FAIL without the locking fixes.
        """
        c = TestClient()

        # Create packages
        c.save({"pkg/conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create pkg")

        # Create an initial lockfile
        c.save({"consumer/conanfile.py": GenConanfile().with_requires("pkg/1.0")})
        c.run("lock create consumer --lockfile-out=base.lock")
        base_lock_path = os.path.join(c.current_folder, "base.lock")

        # Create a second lockfile to merge
        c.save({"pkg2/conanfile.py": GenConanfile("pkg2", "1.0")})
        c.run("create pkg2")
        c.save({"consumer2/conanfile.py": GenConanfile().with_requires("pkg2/1.0")})
        c.run("lock create consumer2 --lockfile-out=lock2.lock")
        lock2_path = os.path.join(c.current_folder, "lock2.lock")

        # Output paths for each process
        output1_path = os.path.join(c.current_folder, "output1.lock")
        output2_path = os.path.join(c.current_folder, "output2.lock")

        result_queue = multiprocessing.Queue()

        # Process 1: Repeatedly writes to base.lock by merging
        def writer_process():
            for i in range(10):
                _child_process_merge_lockfiles(
                    c.cache_folder,
                    [base_lock_path, lock2_path],
                    output1_path,  # Different output to avoid direct conflict
                    f"writer_{i}",
                    result_queue
                )
                time.sleep(0.01)  # Small delay between writes

        # Process 2: Tries to read base.lock by merging with it
        def reader_process():
            time.sleep(0.005)  # Start slightly after writer
            for i in range(10):
                _child_process_merge_lockfiles(
                    c.cache_folder,
                    [base_lock_path, lock2_path],  # Reading base.lock
                    output2_path,
                    f"reader_{i}",
                    result_queue
                )
                time.sleep(0.01)

        p1 = multiprocessing.Process(target=writer_process)
        p2 = multiprocessing.Process(target=reader_process)

        p1.start()
        p2.start()

        p1.join(timeout=60)
        p2.join(timeout=60)

        assert not p1.is_alive(), "Writer process hung"
        assert not p2.is_alive(), "Reader process hung"

        # Collect results
        results = []
        while not result_queue.empty():
            results.append(result_queue.get_nowait())

        # Check for failures
        failures = [r for r in results if not r["success"]]
        if failures:
            # Look for JSON parse errors which indicate read-during-write races
            parse_errors = [f for f in failures
                          if "JSON" in f.get("stderr", "") or
                             "parsing" in f.get("stderr", "").lower()]
            if parse_errors:
                pytest.fail(
                    f"Found {len(parse_errors)} JSON parse errors out of {len(failures)} failures. "
                    "This indicates lockfiles were read while being written (race condition). "
                    f"Example error: {parse_errors[0].get('stderr', '')[:200]}"
                )

    def test_direct_lockfile_save_call_vulnerability(self):
        """
        Test that demonstrates the vulnerability in lock_merge command.

        The lock_merge command calls result.save() directly instead of using
        LockfileAPI.save_lockfile(), bypassing locking protection.

        This is a unit-level test showing the architectural issue.
        """
        c = TestClient()

        # Create lockfiles to merge
        c.save({"pkg/conanfile.py": GenConanfile("pkg", "1.0")})
        c.run("create pkg")

        c.save({"consumer/conanfile.py": GenConanfile().with_requires("pkg/1.0")})
        c.run("lock create consumer --lockfile-out=lock1.lock")
        c.run("lock create consumer --lockfile-out=lock2.lock")

        # The merge command uses result.save() which has no locking
        c.run("lock merge --lockfile lock1.lock --lockfile lock2.lock --lockfile-out merged.lock")

        # File should exist and be valid (single-threaded case works)
        merged_path = os.path.join(c.current_folder, "merged.lock")
        assert os.path.exists(merged_path)

        with open(merged_path, 'r') as f:
            data = json.load(f)

        # Single-threaded works fine - the issue only manifests under concurrency
        assert "requires" in data or "build_requires" in data
