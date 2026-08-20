import io
import json
import os
import platform
import shutil
import stat
import sys
import tarfile
import textwrap
import time
from unittest.mock import patch

import pytest

from conan.api.model import PkgReference, RecipeReference
from conan.errors import ConanException
from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.test_files import temp_folder
from conan.test.utils.tools import TestClient, NO_SETTINGS_PACKAGE_ID
from conan.internal.util.files import is_dirty, load, save, set_dirty


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


_READ_ONLY_CONANFILE = textwrap.dedent("""
    import os, stat
    from conan import ConanFile
    from conan.tools.files import save

    class Pkg(ConanFile):
        name = "pkg"
        version = "1.0"
        def package(self):
            f = os.path.join(self.package_folder, "bin", "readonly.txt")
            save(self, f, "content!!")
            d = os.path.join(self.package_folder, "readonlydir")
            save(self, os.path.join(d, "inside.txt"), "inside!!")
            os.chmod(f, stat.S_IREAD)
            os.chmod(d, stat.S_IREAD | stat.S_IEXEC)
    """)


def _pkg_folder(client):
    ref_layout = client.get_latest_ref_layout(RecipeReference.loads("pkg/1.0"))
    pkg_layout = client.get_latest_pkg_layout(PkgReference(ref_layout.reference,
                                                           NO_SETTINGS_PACKAGE_ID))
    return pkg_layout.package()


def _save_built_package():
    """ a package built in this cache, so it lives in the "b" build folder, not in the final
    package folder that it will have when it is restored in another cache """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports_sources("*.c")
                                                      .with_package_file("bin/f.txt", "content!!"),
            "mysrc.c": "source!!"})
    c.run("create .")
    c.run("cache save *:*")
    return c, os.path.join(c.current_folder, "conan_cache_save.tgz")


def test_cache_restore_no_leftovers():
    """ every folder is extracted directly in its final location, so the folders of the origin
    cache are not created, and the "pkglist.json" is not left in the cache either """
    _, cache_path = _save_built_package()

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    store = os.path.join(c2.cache_folder, "p")
    assert not os.path.exists(os.path.join(store, "b"))
    assert not os.path.exists(os.path.join(store, "pkglist.json"))
    assert load(os.path.join(_pkg_folder(c2), "bin", "f.txt")) == "content!!"


def test_cache_restore_existing_contents_not_extracted():
    """ recipes and packages are immutable, so a revision already in the cache is not extracted
    again over the existing files """
    _, cache_path = _save_built_package()

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    f = os.path.join(_pkg_folder(c2), "bin", "f.txt")
    save(f, "not overwritten")
    c2.run(f'cache restore "{cache_path}"')
    assert load(f) == "not overwritten"


def test_cache_restore_stale_contents():
    """ contents in the cache store that the DB doesn't know about are not valid contents, they
    are leftovers, so they are replaced by the ones in the archive """
    _, cache_path = _save_built_package()

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    pkg_folder = _pkg_folder(c2)
    save(os.path.join(pkg_folder, "stale.txt"), "stale!!")
    os.remove(os.path.join(c2.cache_folder, "p", "cache.sqlite3"))  # The folders are orphans now

    c2.run(f'cache restore "{cache_path}"')
    assert not os.path.exists(os.path.join(pkg_folder, "stale.txt"))
    assert load(os.path.join(pkg_folder, "bin", "f.txt")) == "content!!"


def _assert_read_only_pkg(client):
    """ Check the packaged read-only contents and return their permission modes """
    pkg_folder = _pkg_folder(client)
    f = os.path.join(pkg_folder, "bin", "readonly.txt")
    d = os.path.join(pkg_folder, "readonlydir")
    assert load(f) == "content!!"
    assert load(os.path.join(d, "inside.txt")) == "inside!!"
    modes = stat.S_IMODE(os.stat(f).st_mode), stat.S_IMODE(os.stat(d).st_mode)
    assert (modes[0] & stat.S_IWRITE) == 0
    assert (modes[1] & stat.S_IWRITE) == 0
    return modes


def test_cache_restore_read_only_files_in_place():
    """ restoring over a cache that already contains those same read-only files
    https://github.com/conan-io/conan/issues/20241
    """
    c = TestClient()
    c.save({"conanfile.py": _READ_ONLY_CONANFILE})
    c.run("create .")
    modes = _assert_read_only_pkg(c)
    c.run("cache save *:*")
    c.run("cache restore conan_cache_save.tgz")
    # The revision is already in the cache, the read-only contents are not extracted again
    assert _assert_read_only_pkg(c) == modes


def test_cache_save_restore_read_only_files():
    """ restoring in a different cache, the package folder is relocated, and restoring again
    happens over the read-only files of the previous restore
    https://github.com/conan-io/conan/issues/20241
    """
    c = TestClient()
    c.save({"conanfile.py": _READ_ONLY_CONANFILE})
    c.run("create .")
    modes = _assert_read_only_pkg(c)
    c.run("cache save *:*")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    # The extraction restores the modes stored in the archive, they are still read-only
    assert _assert_read_only_pkg(c2) == modes
    c2.run(f'cache restore "{cache_path}"')
    assert _assert_read_only_pkg(c2) == modes


def test_cache_restore_dirty_folders():
    """ the folders left incomplete by an interrupted restore are dirty, so they are replaced
    by the next restore, not skipped as if they were valid """
    _, cache_path = _save_built_package()

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    pkg_folder = _pkg_folder(c2)
    src_folder = c2.get_latest_ref_layout(RecipeReference.loads("pkg/1.0")).source()
    save(os.path.join(pkg_folder, "bin", "f.txt"), "incomplete")
    save(os.path.join(src_folder, "mysrc.c"), "incomplete")
    set_dirty(pkg_folder)
    set_dirty(src_folder)

    c2.run(f'cache restore "{cache_path}"')
    assert load(os.path.join(pkg_folder, "bin", "f.txt")) == "content!!"
    assert load(os.path.join(src_folder, "mysrc.c")) == "source!!"
    assert not is_dirty(pkg_folder)
    assert not is_dirty(src_folder)


def test_cache_restore_rejects_outside_paths():
    """ a parent-directory tar member must not be written outside the package-cache store
    """
    _, cache_path = _save_built_package()
    file_name = "../outside.txt"
    tar_file = os.path.join(os.path.dirname(cache_path), "cache.tgz")

    with tarfile.open(cache_path, "r:gz") as inn, tarfile.open(tar_file, "w:gz") as out:
        for member in inn.getmembers():
            out.addfile(member, inn.extractfile(member) if member.isfile() else None)
        payload = b"outside!!"
        info = tarfile.TarInfo(name=file_name)
        info.size = len(payload)
        out.addfile(info, io.BytesIO(payload))

    c2 = TestClient()
    c2.run(f'cache restore "{tar_file}"')
    store = os.path.join(c2.cache_folder, "p")
    outside = os.path.normpath(os.path.join(store, file_name))
    # outside file is not restored
    assert not os.path.exists(outside)
    # check the package was restored
    assert load(os.path.join(_pkg_folder(c2), "bin", "f.txt")) == "content!!"


@pytest.mark.parametrize("extractions", [0, 2])
def test_cache_restore_failure_removes_new_entries(extractions):
    """ if the restore fails, the new DB entries whose contents were not restored are removed,
    so the cache is never left with references to recipes or packages that are not there """
    _, cache_path = _save_built_package()
    extract_all = tarfile.TarFile.extractall
    done = []

    def failing_extractall(self, *args, **kwargs):
        if len(done) == extractions:
            raise ConanException("Interrupted!")
        done.append(1)
        return extract_all(self, *args, **kwargs)

    c2 = TestClient()
    with patch.object(tarfile.TarFile, "extractall", failing_extractall):
        c2.run(f'cache restore "{cache_path}"', assert_error=True)
    assert "Interrupted!" in c2.out
    c2.run("list *:*#*")
    assert "pkg/1.0" not in c2.out
    assert os.listdir(os.path.join(c2.cache_folder, "p")) == ["cache.sqlite3"]

    # The restore can be done again, and it works
    c2.run(f'cache restore "{cache_path}"')
    c2.run("list *:*#*")
    assert "pkg/1.0" in c2.out
    assert load(os.path.join(_pkg_folder(c2), "bin", "f.txt")) == "content!!"


def test_cache_restore_missing_folders():
    """ contents are skipped folder by folder, so an archive can complete a recipe revision
    already in the cache, like adding the sources that it didn't have """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0").with_exports_sources("*.c"),
            "mysrc.c": ""})
    c.run("create .")
    c.run("cache save *:* --no-source --file=nosource.tgz")
    c.run("cache save *:* --file=full.tgz")
    no_source = os.path.join(c.current_folder, "nosource.tgz")
    full = os.path.join(c.current_folder, "full.tgz")

    c2 = TestClient()
    c2.run(f'cache restore "{no_source}"')
    src = c2.get_latest_ref_layout(RecipeReference.loads("pkg/1.0")).source()
    assert not os.path.exists(os.path.join(src, "mysrc.c"))
    c2.run(f'cache restore "{full}"')
    assert os.path.exists(os.path.join(src, "mysrc.c"))


def test_cache_restore_metadata_incremental():
    """ metadata is not immutable, it is restored adding to the existing metadata """
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    c.run("create .")
    pid = c.created_package_id("pkg/1.0")
    c.run(f"cache path pkg/1.0:{pid} --folder=metadata")
    save(os.path.join(str(c.stdout).strip(), "logs", "saved.txt"), "saved!!")
    c.run("cache save *:*")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")

    c2 = TestClient()
    c2.run(f'cache restore "{cache_path}"')
    c2.run(f"cache path pkg/1.0:{pid} --folder=metadata")
    metadata = str(c2.stdout).strip()
    save(os.path.join(metadata, "logs", "mine.txt"), "mine!!")
    c2.run(f'cache restore "{cache_path}"')
    assert load(os.path.join(metadata, "logs", "saved.txt")) == "saved!!"
    assert load(os.path.join(metadata, "logs", "mine.txt")) == "mine!!"


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


def test_cache_save_excluded_folders():
    # https://github.com/conan-io/conan/issues/18234
    c = TestClient(default_server_user=True)
    c.save({"conanfile.py": GenConanfile().with_exports("*.py").with_exports_sources("*.c"),
            "somefile.py": "",
            "mysrc.c": ""})
    c.run("create . --name=pkg --version=1.0")
    ref_layout = c.exported_layout()
    pkg_layout = c.created_layout()
    c.run("upload * --dry-run -r=default -c")
    assert os.path.exists(os.path.join(ref_layout.download_export(), "conan_export.tgz"))
    assert os.path.exists(os.path.join(ref_layout.download_export(), "conan_sources.tgz"))
    assert os.path.exists(os.path.join(ref_layout.source(), "mysrc.c"))
    assert os.path.exists(os.path.join(pkg_layout.download_package(), "conan_package.tgz"))
    assert os.path.exists(pkg_layout.build())

    c.run("cache save *:*")
    cache_path = os.path.join(c.current_folder, "conan_cache_save.tgz")

    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run("cache restore conan_cache_save.tgz")

    ref = RecipeReference.loads("pkg/1.0")
    ref_layout = c2.get_latest_ref_layout(ref)
    pkg_layout = c2.get_latest_pkg_layout(PkgReference(ref_layout.reference, NO_SETTINGS_PACKAGE_ID))
    assert os.path.exists(os.path.join(ref_layout.source(), "mysrc.c"))
    assert not os.path.exists(os.path.join(ref_layout.download_export(), "conan_export.tgz"))
    assert not os.path.exists(os.path.join(ref_layout.download_export(), "conan_sources.tgz"))
    assert not os.path.exists(os.path.join(pkg_layout.download_package(), "conan_package.tgz"))
    assert not os.path.exists(pkg_layout.build())

    # exclude source
    c.run("cache save * --no-source")
    c3 = TestClient()
    shutil.copy2(cache_path, c3.current_folder)
    c3.run("cache restore conan_cache_save.tgz")
    ref_layout = c3.get_latest_ref_layout(ref)
    assert not os.path.exists(os.path.join(ref_layout.source(), "mysrc.c"))


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


# FIXME: check the timestamps of the conan cache restore
@pytest.mark.skipif(platform.system() == "Windows",
                    reason="Fails in windows in ci because of the low precission of the clock")
def test_cache_save_restore_multiple_revisions():
    c = TestClient()
    c.save({"conanfile.py": GenConanfile("pkg", "0.1")})
    c.run("create .")
    rrev1 = c.exported_recipe_revision()
    time.sleep(0.2)
    c.save({"conanfile.py": GenConanfile("pkg", "0.1").with_class_attribute("var=42")})
    c.run("create .")
    rrev2 = c.exported_recipe_revision()
    time.sleep(0.2)
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


@pytest.mark.parametrize("compress", ["gz", "xz", "zst"])
def test_cache_save_restore_compressions(compress):
    """ we accept different compressions formats"""
    if compress == "zst" and sys.version_info.minor < 14:
        pytest.skip("Skipping zst compression tests")

    conan_file = GenConanfile() \
        .with_settings("os") \
        .with_package_file("bin/file.txt", "content!!")

    client = TestClient()
    client.save({"conanfile.py": conan_file})
    client.run("create . --name=pkg --version=1.0 -s os=Linux")
    client.run(f"cache save pkg/*:* --file=mysave.t{compress}")
    if compress in ("xz", "zst"):
        assert f"WARN: experimental: The '{compress}' compression is experimental." in client.out
    cache_path = os.path.join(client.current_folder, f"mysave.t{compress}")
    assert os.path.exists(cache_path)

    c2 = TestClient()
    shutil.copy2(cache_path, c2.current_folder)
    c2.run(f"cache restore mysave.t{compress}")
    c2.run("list *:*#*")
    assert "pkg/1.0" in c2.out
