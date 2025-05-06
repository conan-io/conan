import os
import subprocess

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient


def test_parallel_config_subprocess():
    """Validate that subprocesses can run concurrently without issues.

       This test starts 30 separate subprocesses, each running the `conan config install` command.
       No command should fail, and the cache should be updated correctly.

       We can not use ThreadPoolExecutor neither multiprocessing.Process because they are not
       compatible with fasteners, resulting in concurrency issues.
    """
    workers = 30
    extra_folder = temp_folder(path_with_spaces=False)
    cache_folder = temp_folder(path_with_spaces=False)
    env = os.environ.copy()
    env["CONAN_HOME"] = cache_folder

    test_client = TestClient(cache_folder=cache_folder)
    test_client.run("profile detect --force")
    test_client.save({os.path.join(extra_folder, "profiles", "foobar"): "include(default)"})

    processes = []
    for _ in range(workers):
        p = subprocess.Popen([
            "conan", "config", "install", "-vvv", extra_folder, "--type=dir"
        ], env=env, cwd=os.getcwd())
        processes.append(p)
    for p in processes:
        p.wait()
        assert p.returncode == 0, f"Process failed with exit code {p.returncode}"
