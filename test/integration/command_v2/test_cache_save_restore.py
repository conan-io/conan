import json
import os
import shutil
import tarfile

import pytest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient
from conans.util.files import save, load


def test_cache_save_restore():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile().with_settings("os")})
    c.run("create . --name=pkg --version=1.0 -s os=Linux")
    c.run("create . --name=pkg --version=1.1 -s os=Linux")
    c.run("create . --name=other --version=2.0 -s os=Linux")
    # Force the compress level just to make sure it doesn't crash
    c.run("cache save pkg/*:* -cc core.gzip:compresslevel=9")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")
    assert os.path.exists(cache_path)
    _validate_restore(cache_path)

    # Lets test that the pkglist does not contain windows backslash paths to make it portable
    with open(cache_path, mode='rb') as file_handler:
        the_tar = tarfile.open(fileobj=file_handler)
        fileobj = the_tar.extractfile("pkglist.json")
        pkglist = fileobj.read()
        the_tar.close()

    package_list = json.loads(pkglist)
    assert "\\" not in package_list


def test_cache_save_restore_with_package_file():
    """If we have some sources in the root (like the CMakeLists.txt)
    we don't declare folders.source"""
    conan_file = GenConanfile() \
        .with_settings("os") \
        .with_package_file("bin/file.txt", "content!!")

    client = TestClient()
    client.save({"conanfile.py": conan_file})
    client.run("create . --name=pkg --version=1.0 -s os=Linux")
    client.run("cache save pkg/*:* ")
    cache_path = os.path.join(client.current_folder, "conan_cache_save.tgz")
    assert os.path.exists(cache_path)

    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("list *:*#*")
    assert "pkg/1.0" in c2.out
    tree = _get_directory_tree(c2.base_folder)

    # Restore again, expect the tree to be unchanged
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("list *:*#*")
    assert "pkg/1.0" in c2.out
    tree2 = _get_directory_tree(c2.base_folder)

    assert tree2 == tree


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
    c.run("cache save pkg/*:* ")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")
    assert os.path.exists(cache_path)

    _validate_restore(cache_path)


def _get_directory_tree(base_folder):
    tree = []
    for d, _, fs in os.walk(base_folder):
        rel_d = os.path.relpath(d, base_folder) if d != base_folder else ""
        if rel_d:
            tree.append(rel_d)
        for f in fs:
            tree.append(os.path.join(rel_d, f))
    tree.sort()
    return tree


def _validate_restore(cache_path):
    c2 = TestClient()
    # Create a package in the cache to check put doesn't interact badly
    c2.save({"conanfile.py": GenConanfile().with_settings("os")})
    c2.run("create . --name=pkg2 --version=3.0 -s os=Windows")
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("list *:*#*")
    assert "pkg2/3.0" in c2.out
    assert "pkg/1.0" in c2.out
    assert "pkg/1.1" in c2.out
    assert "other/2.0" not in c2.out
    tree = _get_directory_tree(c2.base_folder)

    # Restore again, just in case
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("list *:*#*")
    assert "pkg2/3.0" in c2.out
    assert "pkg/1.0" in c2.out
    assert "pkg/1.1" in c2.out
    assert "other/2.0" not in c2.out
    tree2 = _get_directory_tree(c2.base_folder)
    assert tree2 == tree


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

    c.run("cache save  pkg/*:* ")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")
    assert os.path.exists(cache_path)

    # restore and check
    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("cache path pkg/1.0 --folder=metadata")
    metadata_path = str(c2.stdout).strip()
    myfile = os.path.join(metadata_path, "logs", "mylogs.txt")
    assert load(myfile) == "mylogs!!!!"
    c2.run(f"cache path pkg/1.0:{pid} --folder=metadata")
    pkg_metadata_path = str(c2.stdout).strip()
    myfile = os.path.join(pkg_metadata_path, "logs", "mybuildlogs.txt")
    assert load(myfile) == "mybuildlogs!!!!"


def test_cache_save_restore_multiple_revisions():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    rrev1 = c.exported_recipe_revision()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("var=42")})
    c.run("create .")
    rrev2 = c.exported_recipe_revision()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("var=123")})
    c.run("create .")
    rrev3 = c.exported_recipe_revision()

    def check_ordered_revisions(client):
        client.run("list *#* --format=json")
        revisions = json.loads(client.stdout)["Local Cache"]["pkg/0.1"]["revisions"]
        assert revisions[rrev1]["timestamp"] < revisions[rrev2]["timestamp"]
        assert revisions[rrev2]["timestamp"] < revisions[rrev3]["timestamp"]

    check_ordered_revisions(c)

    c.run("cache save pkg/*#*:* ")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")

    # restore and check
    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")
    check_ordered_revisions(c2)


def test_cache_save_restore_graph():
    """ It is possible to save package list
    """
    c = TestClient()
    c.save({"dep/conanfile.py": GenConanfile("dep", "0.1"),
            "pkg/conanfile.py": GenConanfile("pkg", "0.1").with_requires("dep/0.1")})
    c.run("create dep")
    c.run("create pkg --format=json", redirect_stdout="graph.json")
    c.run("list --graph=graph.json --format=json", redirect_stdout="list.json")
    c.run("cache save --file=cache.tgz --list=list.json")
    cache_path = os.path.join(c.current_folder, "cache.tgz")
    assert os.path.exists(cache_path)
    c2 = TestClient()
    # Create a package in the cache to check put doesn't interact badly
    c2.save({"conanfile.py": GenConanfile().with_settings("os")})
    c2.run("create . --name=pkg2 --version=3.0 -s os=Windows")
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore cache.tgz")
    c2.run("list *:*#*")
    assert "pkg/0.1" in c2.out
    assert "dep/0.1" in c2.out


def test_cache_save_subfolder():
    """ It is possible to save package list in subfolder that doesn't exist
    https://github.com/conan-io/conan/issues/15362
    """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("dep", "0.1")})
    c.run("export .")
    c.run("cache save * --file=subfolder/cache.tgz")
    assert os.path.exists(os.path.join(c.current_folder, "subfolder", "cache.tgz"))


def test_error_restore_not_existing():
    c = TestClient()
    c.run("cache restore potato.tgz", assert_error=True)
    assert "ERROR: Restore archive doesn't exist in " in c.out


@pytest.mark.parametrize("src_store", (False, True))
@pytest.mark.parametrize("dst_store", (False, True))
def test_cache_save_restore_custom_storage_path(src_store, dst_store):
    c = TestClient()
    if src_store:
        tmp_folder = temp_folder()
        c.save_home({"global.conf": f"core.cache:storage_path={tmp_folder}"})
    c.save({"conanfile.py": GenConanfile()})
    c.run("create . --name=pkg --version=1.0")
    c.run("cache save *:*")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")

    c2 = TestClient()
    if dst_store:
        tmp_folder = temp_folder()
        c2.save_home({"global.conf": f"core.cache:storage_path={tmp_folder}"})
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")
    c2.run("list *:*")
    assert "pkg/1.0" in c2.out
