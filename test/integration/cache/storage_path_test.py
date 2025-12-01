import os
import textwrap
from hashlib import sha256

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


def test_wrong_home_error():
    client = TestClient(light=True)
    client.save_home({"global.conf": "core.cache:storage_path=//"})
    client.run("list *")
    assert "Couldn't initialize storage in" in client.out


def test_short_storage_path():
    c = TestClient()
    global_conf = textwrap.dedent("""\
        {% set h = hashlib.new("sha256", conan_home_folder.encode(),
                               usedforsecurity=False).hexdigest() %}
        core.cache:storage_path=C:/conan_{{h[:6]}}
        """)
    c.save_home({"global.conf": global_conf})
    c.run("config show *")
    myhash = sha256()
    myhash.update(c.cache_folder.replace("\\", "/").encode())
    myhash = myhash.hexdigest()[:6]
    assert f"core.cache:storage_path: C:/conan_{myhash}" in c.out
