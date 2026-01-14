"""
Stress tests for lockfile merge concurrency.

These tests spawn multiple subprocesses and are resource-intensive. They are separated
from the main test suite to avoid environmental sensitivity when run after thousands
of other tests.
"""

import json
import multiprocessing
import os
import tempfile

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient
from test.utils.multiprocess import MultiProcessTestClient


# Helper function for multiprocessing - must be at module level to be picklable
def _child_process_create_and_merge(cache_folder, conanfile_content, pkg_name,
                                    pkg_version, merge_with, output_path,
                                    process_id, result_queue):
    """
    Child process that creates a lockfile and then merges it with another.

    This simulates a common CI/CD pattern where parallel jobs each create their
    own lockfile and then merge them together.

    Args:
        cache_folder: Path to the shared cache folder
        conanfile_content: Content of conanfile.py
        pkg_name: Package name to create
        pkg_version: Package version
        merge_with: Path to lockfile to merge with (or None)
        output_path: Path for the merged output
        process_id: ID for this process
        result_queue: multiprocessing.Queue to report results
    """
    import sys
    import subprocess
    import json

    try:
        # Set up environment
        env = os.environ.copy()
        env["CONAN_HOME"] = cache_folder

        # Ensure subprocess uses the same conan module as the test runner
        # by adding the conan source directory to PYTHONPATH
        import conan
        conan_source_dir = os.path.dirname(os.path.dirname(conan.__file__))
        if "PYTHONPATH" in env:
            env["PYTHONPATH"] = f"{conan_source_dir}{os.pathsep}{env['PYTHONPATH']}"
        else:
            env["PYTHONPATH"] = conan_source_dir

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write conanfile
            conanfile_path = os.path.join(tmpdir, "conanfile.py")
            with open(conanfile_path, "w") as f:
                f.write(conanfile_content)

            # Create package (increased timeout for resource-constrained environments)
            cmd = [sys.executable, "-m", "conans.conan", "create", ".",
                   f"--name={pkg_name}", f"--version={pkg_version}"]
            result = subprocess.run(cmd, env=env, cwd=tmpdir, capture_output=True,
                                  text=True, timeout=120)
            if result.returncode != 0:
                result_queue.put({
                    "success": False,
                    "process_id": process_id,
                    "stage": "create",
                    "stderr": result.stderr,
                    "returncode": result.returncode
                })
                return
            # Report create success
            result_queue.put({
                "success": True,
                "process_id": process_id,
                "stage": "create",
                "message": f"Successfully created {pkg_name}/{pkg_version}"
            })

            # Create lockfile for this package
            lockfile_path = os.path.join(tmpdir, f"lock_{process_id}.lock")
            cmd = [sys.executable, "-m", "conans.conan", "lock", "create", ".",
                   f"--lockfile-out={lockfile_path}"]
            result = subprocess.run(cmd, env=env, cwd=tmpdir, capture_output=True,
                                  text=True, timeout=120)
            if result.returncode != 0:
                result_queue.put({
                    "success": False,
                    "process_id": process_id,
                    "stage": "lock_create",
                    "stderr": result.stderr,
                    "returncode": result.returncode
                })
                return

            # Verify lockfile was created
            if not os.path.exists(lockfile_path):
                result_queue.put({
                    "success": False,
                    "process_id": process_id,
                    "stage": "lock_create",
                    "error": f"Lockfile not created at {lockfile_path}"
                })
                return

            # Read the lockfile content to verify what package it contains
            with open(lockfile_path, 'r') as f:
                lockfile_content = f.read()

            # Report lock create success
            result_queue.put({
                "success": True,
                "process_id": process_id,
                "stage": "lock_create",
                "message": f"Successfully created lockfile at {lockfile_path}",
                "lockfile_content": lockfile_content[:500]  # First 500 chars
            })

            # Merge with another lockfile if provided, or with existing output file
            # Note: The lock_merge command automatically includes the output file in the merge
            # (see conan/cli/commands/lock.py line 79), so we only need to pass our lockfile
            if merge_with and os.path.exists(merge_with):
                # Explicit merge_with file provided
                cmd = [sys.executable, "-m", "conans.conan", "lock", "merge",
                       "--lockfile", lockfile_path,
                       "--lockfile", merge_with,
                       "--lockfile-out", output_path]
            else:
                # Concurrent merge pattern: lock_merge will automatically merge with output file
                # The first process will create it, subsequent ones will merge with it
                # The lock in lock_merge ensures these operations are serialized
                cmd = [sys.executable, "-m", "conans.conan", "lock", "merge",
                       "--lockfile", lockfile_path,
                       "--lockfile-out", output_path]

            result = subprocess.run(cmd, env=env, capture_output=True,
                                  text=True, timeout=120)

            # Read the final output file to see what was written
            final_content = None
            try:
                if os.path.exists(output_path):
                    with open(output_path, 'r') as f:
                        final_data = json.load(f)
                        final_requires = final_data.get('requires', [])
                        final_req_names = [r if isinstance(r, str) else r[0] for r in final_requires]
                        final_content = f"Output has {len(final_req_names)} packages: {final_req_names}"
            except Exception as e:
                final_content = f"Error reading output: {e}"

            # Always report merge result with full details
            result_queue.put({
                "success": result.returncode == 0,
                "process_id": process_id,
                "stage": "merge",
                "returncode": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "message": f"Merge completed with returncode {result.returncode}",
                "final_output": final_content
            })
    except Exception as e:
        result_queue.put({
            "success": False,
            "process_id": process_id,
            "error": str(e)
        })


class TestLockfileMergeStress:
    """
    Stress tests for lockfile merge operations under heavy load.

    These tests spawn multiple subprocesses and can be resource-intensive.
    They are separated to run independently of the main test suite.
    """

    @pytest.mark.slow
    def test_parallel_ci_merge_pattern(self):
        """
        Test a realistic CI/CD pattern: parallel jobs create lockfiles, then merge.

        This simulates:
        1. Multiple parallel CI jobs, each building a different package
        2. Each job creates its own lockfile
        3. A final step merges all lockfiles together

        Previously, concurrent merges to the same output file could lose updates
        due to the read-modify-write race condition. This has been fixed by
        wrapping the entire merge operation in a lock on the output file.

        This test verifies all packages make it into the final merged lockfile.

        Note: This is marked as @pytest.mark.slow because it spawns multiple
        subprocesses and can be resource-intensive. Run separately from the main
        test suite to avoid environmental sensitivity.
        """
        with tempfile.TemporaryDirectory() as cache_folder:
            client = MultiProcessTestClient(cache_folder)

            # Run parallel processes, each creating and merging their lockfile
            num_processes = 3

            # Set up the cache with some packages
            # Use a TestClient first to ensure cache is fully initialized (migrations, DB setup, etc)
            # This prevents concurrent initialization races in the spawned subprocesses
            setup_client = TestClient(cache_folder=cache_folder)
            setup_client.run("version")  # Trigger cache initialization

            for i in range(num_processes):
                setup_client.save({
                    f"pkg{i}/conanfile.py": GenConanfile(f"pkg{i}", "1.0")
                })
                setup_client.run(f"create pkg{i}")

            # Verify cache is properly initialized by checking that all packages are accessible
            # This ensures DB writes are committed and cache is in a consistent state
            setup_client.run("list *")

            # Explicitly close any DB connections to ensure they're released before spawning processes
            # This prevents connection/lock leaks that could cause issues in spawned subprocesses
            del setup_client

            # Shared final output
            final_output = os.path.join(cache_folder, "final_merged.lock")

            # Ensure the output file doesn't exist before starting
            # This prevents any potential issues with stale files
            if os.path.exists(final_output):
                os.remove(final_output)

            # Create base conanfile content
            conanfile_base = """
from conan import ConanFile

class Consumer(ConanFile):
    settings = "os", "compiler", "build_type", "arch"

    def requirements(self):
        self.requires("{pkg_name}/1.0")
"""

            # Use spawn context to avoid fork issues in pytest
            mp_context = multiprocessing.get_context('spawn')
            result_queue = mp_context.Queue()
            processes = []

            for i in range(num_processes):
                conanfile = conanfile_base.format(pkg_name=f"pkg{i}")
                p = mp_context.Process(
                    target=_child_process_create_and_merge,
                    args=(cache_folder, conanfile, f"consumer{i}", "1.0",
                          None, final_output, i, result_queue)
                )
                processes.append(p)

            # Start all processes simultaneously (simulating parallel CI jobs)
            for p in processes:
                p.start()

            # Wait for completion
            for p in processes:
                p.join(timeout=360)
                if p.is_alive():
                    p.terminate()
                    p.join()
                    pytest.fail("Process did not complete - possible deadlock or resource exhaustion")

            # Collect results
            results = []
            while not result_queue.empty():
                results.append(result_queue.get_nowait())

            # Clean up multiprocessing resources explicitly
            # After many tests, it's important to release resources properly
            result_queue.close()
            result_queue.join_thread()
            for p in processes:
                p.close()

            # Organize results by process and stage
            by_process = {}
            for r in results:
                pid = r["process_id"]
                if pid not in by_process:
                    by_process[pid] = []
                by_process[pid].append(r)

            # Build detailed status report
            status_lines = ["\n=== Process Status Report ==="]
            for pid in sorted(by_process.keys()):
                stages = by_process[pid]
                status_lines.append(f"\nProcess {pid}:")
                for stage_result in stages:
                    stage = stage_result.get('stage', 'unknown')
                    success = stage_result.get('success', False)
                    status = "✓" if success else "✗"
                    msg = stage_result.get('message', stage_result.get('error', ''))
                    status_lines.append(f"  {status} {stage}: {msg}")
                    # Show lockfile content for lock_create stage
                    if stage == 'lock_create' and 'lockfile_content' in stage_result:
                        import json as json_lib
                        try:
                            lf_data = json_lib.loads(stage_result['lockfile_content'])
                            requires = lf_data.get('requires', [])
                            req_names = [r if isinstance(r, str) else r[0] for r in requires]
                            status_lines.append(f"    packages: {req_names}")
                        except:
                            pass
                    # Show final output content for merge stage
                    if stage == 'merge' and 'final_output' in stage_result:
                        status_lines.append(f"    {stage_result['final_output']}")
                    if not success:
                        if 'stderr' in stage_result:
                            status_lines.append(f"    stderr: {stage_result['stderr'][:1000]}")
                        if 'stdout' in stage_result:
                            status_lines.append(f"    stdout: {stage_result.get('stdout', '')[:500]}")

            # Count final merge operations (should be num_processes)
            merge_operations = [r for r in results if r.get('stage') == 'merge']
            successful_merges = [r for r in merge_operations if r.get('success')]
            status_lines.append(f"\n=== Summary ===")
            status_lines.append(f"Total merge operations: {len(merge_operations)}")
            status_lines.append(f"Successful merges: {len(successful_merges)}")

            # Check for failures in any stage
            failures = [r for r in results if not r["success"]]
            if failures:
                error_msgs = "\n".join(status_lines)
                pytest.fail(f"Some processes failed:{error_msgs}")

            # Verify the final merged lockfile exists and is valid
            assert os.path.exists(final_output), "Final merged lockfile should exist"

            try:
                with open(final_output, 'r') as f:
                    merged_data = json.load(f)

                # It should contain at least one package (exact result depends on race)
                requires = merged_data.get("requires", [])
                assert len(requires) > 0, "Merged lockfile should have some requires"

                # Verify all packages are present (this is the key test)
                require_names = [r if isinstance(r, str) else r[0] for r in requires]

                # Count packages in the merged lockfile
                found_pkgs = sum(1 for req in require_names
                               if any(f"pkg{i}" in req for i in range(num_processes)))

                # With proper locking, all packages should be in the merged lockfile
                status_report = "\n".join(status_lines)
                assert found_pkgs == num_processes, (
                    f"Should have all {num_processes} packages in merged lockfile, found {found_pkgs}. "
                    f"Requires: {require_names}. "
                    f"All concurrent merges should be serialized by the lock.\n"
                    f"{status_report}"
                )

            except json.JSONDecodeError as e:
                pytest.fail(f"Final merged lockfile is corrupted: {e}")
