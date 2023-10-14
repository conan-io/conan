import os
import shutil

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient
from conans.util.files import save, load


def test_cache_save_restore():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=1.0 -s os=Linux")
    c.run("create . --name=pkg --version=1.1 -s os=Linux")
    c.run("create . --name=other --version=2.0 -s os=Linux")
    c.run("cache save cache.tgz pkg/*:* ")
    cache_path = os.path.join(c.current_folder, "cache.tgz")
    assert os.path.exists(cache_path)
    _validate_restore(cache_path)


def test_cache_save_downloaded_restore():
    """ what happens if we save packages downloaded from server, not
    created
    """
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=1.0 -s os=Linux")
    c.run("create . --name=pkg --version=1.1 -s os=Linux")
    c.run("create . --name=other --version=2.0 -s os=Linux")
    c.run("upload * -r=default -c")
    c.run("remove * -c")
    c.run("download *:* -r=default --metadata=*")
    c.run("cache save cache.tgz pkg/*:* ")
    cache_path = os.path.join(c.current_folder, "cache.tgz")
    assert os.path.exists(cache_path)

    _validate_restore(cache_path)


def _validate_restore(cache_path):
    c2 = TestClient()
    # Create a package in the cache to check put doesn't interact badly
    c2.save({"conanfile.py": GenConanfile().with_settings("os")})
    c2.run("create . --name=pkg2 --version=3.0 -s os=Windows")
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore cache.tgz")
    c2.run("list *:*#*")
    assert "pkg2/3.0" in c2.out
    assert "pkg/1.0" in c2.out
    assert "pkg/1.1" in c2.out
    assert "other/2.0" not in c2.out

    # Restore again, just in case
    c2.run("cache restore cache.tgz")
    c2.run("list *:*#*")
    assert "pkg2/3.0" in c2.out
    assert "pkg/1.0" in c2.out
    assert "pkg/1.1" in c2.out
    assert "other/2.0" not in c2.out


def test_cache_save_restore_metadata():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=1.0 -s os=Linux")
    pid = c.created_package_id("pkg/1.0")
    # Add some metadata
    c.run("cache path pkg/1.0 --folder=metadata")
    metadata_path = str(c.stdout).strip()
    myfile = os.path.join(metadata_path, "logs", "mylogs.txt")
    save(myfile, "mylogs!!!!")
    c.run(f"cache path pkg/1.0:{pid} --folder=metadata")
    pkg_metadata_path = str(c.stdout).strip()
    myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt")
    save(myfile, "mybuildlogs!!!!")

    c.run("cache save cache.tgz pkg/*:* ")
    cache_path = os.path.join(c.current_folder, "cache.tgz")
    assert os.path.exists(cache_path)

    # restore and check
    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore cache.tgz")
    c2.run("cache path pkg/1.0 --folder=metadata")
    metadata_path = str(c2.stdout).strip()
    myfile = os.path.join(metadata_path, "logs", "mylogs.txt")
    assert load(myfile) == "mylogs!!!!"
    c2.run(f"cache path pkg/1.0:{pid} --folder=metadata")
    pkg_metadata_path = str(c2.stdout).strip()
    myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt")
    assert load(myfile) == "mybuildlogs!!!!"
