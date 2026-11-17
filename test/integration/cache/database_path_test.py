import os
import sqlite3

import pytest

from conan.test.utils.tools import GenConanfile, TestClient


@pytest.mark.parametrize("custom_storage", [False, True])
@pytest.mark.parametrize("config_install", [False, True])
def test_database_path(tmp_path, custom_storage, config_install):
    client = TestClient()
    database = tmp_path / "database with spaces"
    storage = tmp_path / "packages" if custom_storage else os.path.join(client.cache_folder, "p")
    conf = f"core.cache:root_database_folder={database}"
    if custom_storage:
        conf += f"\ncore.cache:storage_path={storage}"
    if config_install:
        client.save({"config/global.conf": conf})
        client.run('config install "config"')
    else:
        client.save_home({"global.conf": conf})
    client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("file.txt", "data")})
    client.run("create .")
    database = next(database.glob("*/cache.sqlite3")).parent
    package_folder = client.created_layout().package()
    assert os.path.commonpath([package_folder, str(storage)]) == str(storage)
    with open(os.path.join(package_folder, "file.txt")) as handle:
        assert handle.read() == "data"
    client.run("install --requires=pkg/1.0 --no-remote")
    assert "Already installed!" in client.out
    client.run("cache path pkg/1.0")
    assert str(storage) in client.out
    assert (database / "cache.sqlite3").is_file()
    with sqlite3.connect(database / "cache.sqlite3") as connection:
        assert connection.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert connection.execute("SELECT count(*) FROM recipes").fetchone() == (1,)
        assert connection.execute("SELECT count(*) FROM packages").fetchone() == (1,)
        connection.execute("BEGIN IMMEDIATE")
        connection.execute("UPDATE recipes SET timestamp = timestamp + 1")
        assert (database / "cache.sqlite3-journal").is_file()
        connection.rollback()
    client.run("remove pkg/1.0 -c")
    client.run("list pkg/1.0")
    assert "Recipe 'pkg/1.0' not found" in client.out


@pytest.mark.parametrize("shared_storage", [False, True])
def test_database_path_isolation(tmp_path, shared_storage):
    first = TestClient(light=True)
    conf = f"core.cache:root_database_folder={tmp_path}"
    first.save_home({"global.conf": conf})
    first.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    first.run("export .")
    assert not os.path.exists(os.path.join(first.cache_folder, "p", "cache.sqlite3"))
    second = TestClient()
    if shared_storage:
        storage = os.path.join(first.cache_folder, "p", ".")
        conf += f"\ncore.cache:storage_path={storage}"
    second.save_home({"global.conf": conf})
    second.run("list pkg/1.0")
    assert ("Recipe 'pkg/1.0' not found" in second.out) == (not shared_storage)
    assert len(list(tmp_path.glob("*/cache.sqlite3"))) == (1 if shared_storage else 2)
    first.run("list pkg/1.0")
    assert "Recipe 'pkg/1.0' not found" not in first.out


def test_database_path_invalid(tmp_path):
    root = tmp_path / "file"
    root.write_text("file", encoding="utf-8")
    client = TestClient(light=True)
    client.save_home({"global.conf": f"core.cache:root_database_folder={root}"})
    client.run("list *", assert_error=True)
    assert "Couldn't initialize storage" in client.out


def test_database_path_lost_database(tmp_path):
    client = TestClient(light=True)
    client.save_home({"global.conf": f"core.cache:root_database_folder={tmp_path}"})
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("export .")
    database = next(tmp_path.glob("*/cache.sqlite3"))
    database.unlink()
    client.run("list pkg/1.0")
    assert "Recipe 'pkg/1.0' not found" in client.out
    assert database.is_file()


@pytest.mark.parametrize("transfer", ["download", "restore"])
def test_database_path_transfer(tmp_path, transfer):
    source = TestClient(default_server_user=True)
    source.save_home({"global.conf": f"core.cache:root_database_folder={tmp_path / 'source'}"})
    source.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("file.txt", "data")})
    source.run("create .")
    target = TestClient(servers=source.servers)
    target.save_home({"global.conf": f"core.cache:root_database_folder={tmp_path / 'target'}"})
    if transfer == "download":
        source.run("upload pkg/1.0 -r=default -c")
        target.run("download pkg/1.0 -r=default")
    else:
        source.run("cache save pkg/1.0:*")
        archive = os.path.join(source.current_folder, "conan_cache_save.tgz")
        target.run(f'cache restore "{archive}"')
    target.run("install --requires=pkg/1.0 --no-remote")
    assert "Already installed!" in target.out
    target.run("cache check-integrity pkg/1.0:*")
    assert "Integrity check: ok" in target.out
