import concurrent.futures
import pytest
from conan.test.utils.test_files import temp_folder
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


def run_parallel_and_check_errors(test_client, operation_func, num_tasks=10, *args):
    """Run operations in parallel and check for expected errors"""
    parallel_known_errors = [
        "Folder might be busy or open",
        "conanfile.py not found",
        "[Errno 17] File exists",
        "[Errno 2] No such file or directory",
        "assert os.path.isfile(path)",
        "raise ConanException",
        "WinError 3",
    ]
    exceptions = []
    while not exceptions:
        with concurrent.futures.ThreadPoolExecutor(max_workers=num_tasks) as executor:
            try:
                futures = [executor.submit(operation_func, test_client, i, *args) for i in range(num_tasks)]
                done_tasks, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_EXCEPTION)

                for task in done_tasks:
                    if task.exception():
                        exceptions.append(task.exception())
            finally:
                executor.shutdown(wait=False, cancel_futures=True)

    for err in exceptions:
        str_err = str(err)
        assert [perror for perror in parallel_known_errors if perror in str_err], f"Unexpected error: {str_err}"


def test_parallel_config():
    """Run multiple conan config install in parallel to test the cache concurrency support."""
    def config_install(test_client, _, cache_folder):
        try:
            test_client.run(f"config install {cache_folder} --type=dir")
        except Exception:
            pass

    cache_folder = temp_folder(path_with_spaces=False)
    test_client_cache = TestClient(cache_folder=cache_folder)
    test_client_cache.run("profile detect --force")
    test_client = TestClient()

    run_parallel_and_check_errors(test_client, config_install, 4, cache_folder)


def test_parallel_export():
    """Run multiple conan export in parallel to test the cache concurrency support."""
    def export(test_client, _):
        try:
            test_client.run("export .")
        except Exception:
            pass

    test_client = TestClient()
    test_client.save({"conanfile.py": GenConanfile("parallel", "0.1.0")})

    run_parallel_and_check_errors(test_client, export, 4)


@pytest.mark.tool("cmake")
def test_parallel_create():
    """Run multiple builds in parallel to test the cache concurrency support."""
    def create(test_client, i):
        options = [
            '-o "&:foo=True" -o "&:qux=True" -o "&:baz=True"',
            '-o "&:foo=False" -o "&:qux=True" -o "&:baz=True"',
            '-o "&:foo=True" -o "&:qux=False" -o "&:baz=True"',
            '-o "&:foo=True" -o "&:qux=True" -o "&:baz=False"',
        ]
        try:
            test_client.run(f"create . {options[i]}")
        except Exception:
            pass

    test_client = TestClient()
    test_client.save({"conanfile.py": GenConanfile("parallel", "0.1.0")
                    .with_option("foo", [True, False])
                    .with_option("qux", [True, False])
                    .with_option("baz", [True, False])
                    .with_default_option("foo", False)
                    .with_default_option("qux", False)
                    .with_default_option("baz", False)})

    run_parallel_and_check_errors(test_client, create, 4)
