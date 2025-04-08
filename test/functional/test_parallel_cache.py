import concurrent.futures
import pytest
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient

_parallel_options = [
    '-o "&:foo=True" -o "&:qux=True" -o "&:baz=True"',
    '-o "&:foo=False" -o "&:qux=True" -o "&:baz=True"',
    '-o "&:foo=True" -o "&:qux=False" -o "&:baz=True"',
    '-o "&:foo=True" -o "&:qux=True" -o "&:baz=False"',
]


def _build_package(build_id, test_client):
    try:
        test_client.run(f"create . {_parallel_options[build_id]}")
    except Exception:
        pass


@pytest.mark.tool("cmake")
def test_parallel_cache():
    """Run multiple builds in parallel to test the cache concurrency support in Conan.

    This test creates a package with multiple options and builds it in parallel using
    different combinations of options. The goal is to ensure that the cache can handle
    concurrent builds without any issues.

    There is no support for this feature in Conan at this moment, but is desired.
    """
    num_builds = len(_parallel_options)
    test_client = TestClient()
    test_client.run("new cmake_lib -d name=parallel -d version=0.1.0")
    test_client.save({"conanfile.py": GenConanfile("parallel", "0.1.0")
                      .with_option("foo", [True, False])
                      .with_option("qux", [True, False])
                      .with_option("baz", [True, False])
                      .with_default_option("foo", False)
                      .with_default_option("qux", False)
                      .with_default_option("baz", False)})

    exceptions = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_builds) as executor:
        try:
            future_to_build = {executor.submit(_build_package, i, test_client): i for i in range(num_builds)}
            done_tasks, not_done_tasks = concurrent.futures.wait(future_to_build, return_when=concurrent.futures.FIRST_EXCEPTION)
            for task in done_tasks:
                if task.exception():
                    exceptions.append(task.exception())
        finally:
            executor.shutdown(wait=False, cancel_futures=True)
        assert exceptions
        for error in exceptions:
            assert "Folder might be busy or open" in str(error) or \
                   "conanfile.py not found" in str(error)
