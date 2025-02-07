import os

from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, GenConanfile


def test_storage_path():
    client = TestClient()
    client.save({"conanfile.py": GenConanfile()})
    tmp_folder = temp_folder(path_with_spaces=True)
    client.save_home({"global.conf": f"core.cache:storage_path={tmp_folder}"})
    client.run("create . --name=mypkg --version=0.1")
    assert f"mypkg/0.1: Package folder {tmp_folder}" in client.out
    assert os.path.isfile(os.path.join(tmp_folder, "cache.sqlite3"))

    client.run("cache path mypkg/0.1")
    assert tmp_folder in client.out
