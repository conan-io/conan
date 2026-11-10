import threading
from unittest.mock import patch

from requests import ConnectionError

from conan.internal import loader
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient, TestRequester


def test_upload_parallel_error():
    """Cause an error in the parallel transfer and see some message"""

    class FailOnReferencesUploader(TestRequester):
        fail_on = ["lib1", "lib3"]

        def put(self, *args, **kwargs):
            if any(ref in args[0] for ref in self.fail_on):
                raise ConnectionError("Connection fails with lib2 and lib4 references!")
            else:
                return super(FailOnReferencesUploader, self).put(*args, **kwargs)

    client = TestClient(requester_class=FailOnReferencesUploader, default_server_user=True)
    client.save_home({"global.conf": f"core.upload:parallel=2\ncore.upload:retry_wait=0"})
    client.save({"conanfile.py": GenConanfile()})
    client.run('remote login default admin -p password')
    for index in range(4):
        client.run('create . --name=lib{} --version=1.0 --user=user --channel=channel'.format(index))
    client.run('upload lib* -c -r default', assert_error=True)
    assert "Connection fails with lib2 and lib4 references!" in client.out
    assert "Execute upload again to retry upload the failed files" in client.out


def test_upload_parallel_success():
    """Upload 2 packages in parallel with success"""

    client = TestClient(default_server_user=True)
    client.save_home({"global.conf": f"core.upload:parallel=2"})
    client.save({"conanfile.py": GenConanfile()})
    client.run('create . --name=lib0 --version=1.0 --user=user --channel=channel')
    client.run('create . --name=lib1 --version=1.0 --user=user --channel=channel')
    client.run('remote login default admin -p password')
    client.run('upload lib* -c -r default')
    assert "Uploading recipe 'lib0/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd'" in client.out
    assert "Uploading recipe 'lib1/1.0@user/channel#4d670581ccb765839f2239cc8dff8fbd'" in client.out
    client.run('search lib0/1.0@user/channel -r default')
    assert "lib0/1.0@user/channel" in client.out
    client.run('search lib1/1.0@user/channel -r default')
    assert "lib1/1.0@user/channel" in client.out


def test_upload_parallel_loader_not_created_in_threads():
    """ Creating a ConanFileLoader calls importlib.invalidate_caches(), which iterates
    sys.path_importer_cache while other upload threads might be loading conanfiles and modifying it,
    randomly failing with "RuntimeError: dictionary changed size during iteration".
    The race itself can't be reproduced deterministically, so check that the loader is created
    only by the calling thread and shared by all the upload threads
    """
    client = TestClient(default_server_user=True, light=True)
    client.save_home({"global.conf": "core.upload:parallel=4"})
    client.save({"tool/conanfile.py": GenConanfile("tool", "1.0"),
                 "lib/conanfile.py": GenConanfile().with_python_requires("tool/1.0")})
    client.run("export tool")
    num_libs = 6
    for index in range(num_libs):
        client.run(f"create lib --name=lib{index} --version=1.0")

    invalidating_threads = set()
    original_invalidate_caches = loader.invalidate_caches

    def _invalidate_caches():
        invalidating_threads.add(threading.current_thread())
        original_invalidate_caches()

    # Login first, otherwise all the threads could ask for the credentials at the same time
    client.run("remote login default admin -p password")
    with patch.object(loader, "invalidate_caches", _invalidate_caches):
        client.run("upload * -c -r default")
    assert invalidating_threads == {threading.current_thread()}
    assert "Uploading with 4 parallel threads" in client.out
    assert "Uploading recipe 'tool/1.0#" in client.out
    for index in range(num_libs):
        assert f"Uploading recipe 'lib{index}/1.0#" in client.out
        assert f"Uploading package 'lib{index}/1.0#" in client.out
    client.run("list *:* -r default")
    for index in range(num_libs):
        assert f"lib{index}/1.0" in client.out


def test_upload_parallel_fail_on_interaction():
    """Upload 2 packages in parallel and fail because non_interactive forced"""
    client = TestClient(default_server_user=True)
    client.save_home({"global.conf": f"core.upload:parallel=2\ncore:non_interactive=True"})
    client.save({"conanfile.py": GenConanfile()})
    num_references = 2
    for index in range(num_references):
        client.run('create . --name=lib{} --version=1.0 --user=user --channel=channel'.format(index))

    client.run('remote logout default')
    client.run('upload lib* -c -r default', assert_error=True)
    assert "ERROR: Conan interactive mode disabled. [Remote: default]" in client.out
