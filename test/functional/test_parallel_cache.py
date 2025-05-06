import os
import subprocess
import re
import multiprocessing as mp

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conan.internal.util.semaphore import interprocess_write_lock, interprocess_read_lock


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


@interprocess_read_lock()
def _reader(shared_file, idx):
    with open(shared_file, "a") as f:
        f.write(f"reader-{idx}-start\n")

    with open(shared_file, "a") as f:
        f.write(f"reader-{idx}-end\n")


@interprocess_write_lock()
def _writer(shared_file, idx):
    with open(shared_file, "a") as f:
        f.write(f"writer-{idx}-start\n")

    with open(shared_file, "a") as f:
        f.write(f"writer-{idx}-end\n")


def test_readers_parallel_writers_exclusive():
    """ Test that multiple readers can run concurrently while writers are exclusive.

        This test uses the interprocess_read_lock and interprocess_write_lock decorators
        to ensure that multiple readers can access the shared file simultaneously,
        while writers have exclusive access.

        The test creates a shared file and starts 5 reader processes and 2 writer processes.
        The readers should be able to run concurrently, while the writers should wait for
        the readers to finish before acquiring the lock.
    """
    cache_folder = temp_folder(path_with_spaces=False)
    shared_file = os.path.join(cache_folder, "shared_rwlock.lock")
    with open(shared_file, "w") as fd:
        fd.write("")

    tasks = [mp.Process(target=_reader, args=(shared_file, i,)) for i in range(5)]
    tasks.extend([mp.Process(target=_writer, args=(shared_file, i,)) for i in range(2)])
    for task in tasks:
        task.start()
    for task in tasks:
        task.join()

    with open(shared_file, "r") as fd:
        lines = fd.readlines()
        assert len(lines) == 14
        for line in lines:
            # No concurrent writes
            assert re.match(r"^(reader|writer)-[0-9]+-(start|end)\n$", line)
