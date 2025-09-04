import os
import sys
import subprocess
import threading

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def _run_config_install(cmd, env, cwd, results, index) -> None:
    """
    Run the command in a subprocess and store the return code in the results list.
    """
    completed = subprocess.run(
        cmd,
        env=env,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    results[index] = completed.returncode
    if completed.returncode:
        print(f"[worker {index}] stderr:\n{completed.stderr}")


def test_parallel_config_subprocess():
    """Validate that subprocesses can run concurrently without issues.

       This test starts 30 separate subprocesses, each running the `conan config install` command.
       No command should fail, and the cache should be updated correctly.
    """
    workers = 30

    extra_folder = temp_folder(path_with_spaces=False)
    cache_folder = temp_folder(path_with_spaces=False)
    env = os.environ.copy()
    env["CONAN_HOME"] = cache_folder

    test_client = TestClient(cache_folder=cache_folder)
    test_client.run("profile detect --force")
    test_client.save({os.path.join(extra_folder, "profiles", "foobar"): "include(default)"})
    cmd = [sys.executable, "-m", "conans.conan", "config", "install", "-vvv", extra_folder, "--type=dir"]

    threads = []
    return_codes = [None] * workers

    for index in range(workers):
        thread = threading.Thread(
            target=_run_config_install,
            args=(cmd, env, os.getcwd(), return_codes, index),
            daemon=True,  # dies with the main program
        )
        thread.start()
        threads.append(thread)

    for thread in threads:
        thread.join()

    assert all(rc == 0 for rc in return_codes), f"Some subprocesses failed: {return_codes}"
