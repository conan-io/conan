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
    conf = f"core.cache:database_path={database}"
    if custom_storage:
        conf += f"\ncore.cache:storage_path={storage}"
    if config_install:
        client.save({"config/global.conf": conf})
        client.run('config install "config"')
    else:
        client.save_home({"global.conf": conf})
    client.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("file.txt", "data")})
    client.run("create .")
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


def test_database_path_existing_cache(tmp_path):
    client = TestClient()
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("create .")
    client.save_home({"global.conf": f"core.cache:database_path={tmp_path}"})
    client.run("list *", assert_error=True)
    assert "requires a fresh cache" in client.out
    assert not (tmp_path / "cache.sqlite3").exists()
    client.save_home({"global.conf": ""})
    client.run("install --requires=pkg/1.0 --no-remote")
    assert "Already installed!" in client.out


@pytest.mark.parametrize("change", ["unset", "change", "missing", "owner"])
def test_database_path_cannot_lose_index(tmp_path, change):
    client = TestClient()
    database = tmp_path / "database"
    client.save_home({"global.conf": f"core.cache:database_path={database}"})
    client.save({"conanfile.py": GenConanfile("pkg", "1.0")})
    client.run("create .")
    if change == "missing":
        (database / "cache.sqlite3").unlink()
    elif change == "owner":
        (database / "cache.sqlite3.storage").write_text("another storage", encoding="utf-8")
    else:
        conf = "" if change == "unset" else f"core.cache:database_path={tmp_path / 'other'}"
        client.save_home({"global.conf": conf})
    client.run("list *", assert_error=True)
    expected = {"missing": "Cache database is missing",
                "owner": "belongs to another package storage"}
    assert expected.get(change, "Cache database location changed") in client.out
    if change == "missing":
        assert not (database / "cache.sqlite3").exists()


def test_database_path_isolation(tmp_path):
    first = TestClient(light=True)
    first.save_home({"global.conf": f"core.cache:database_path={tmp_path}"})
    first.run("list *")
    assert (tmp_path / "cache.sqlite3").is_file()
    assert not os.path.exists(os.path.join(first.cache_folder, "p", "cache.sqlite3"))
    second = TestClient()
    second.save_home({"global.conf": f"core.cache:database_path={tmp_path}"})
    second.run("list *", assert_error=True)
    assert "belongs to another package storage" in second.out
    first.run("list *")


@pytest.mark.parametrize("invalid", ["relative", "file", "unowned"])
def test_database_path_invalid(tmp_path, invalid):
    client = TestClient()
    path = tmp_path
    if invalid == "relative":
        path = "relative/database"
    elif invalid == "file":
        path = tmp_path / "file"
        path.write_text("file", encoding="utf-8")
    else:
        (tmp_path / "cache.sqlite3").write_text("existing database", encoding="utf-8")
    client.save_home({"global.conf": f"core.cache:database_path={path}"})
    client.run("list *", assert_error=True)
    assert "Couldn't initialize storage" in client.out


def test_database_path_storage_directory():
    client = TestClient()
    storage = os.path.join(client.cache_folder, "p")
    client.save_home({"global.conf": f"core.cache:database_path={storage}"})
    client.run("list *")
    assert os.path.isfile(os.path.join(storage, "cache.sqlite3"))
    assert not os.path.exists(os.path.join(storage, "cache.sqlite3.location"))


def test_database_path_missing_location(tmp_path):
    client = TestClient()
    client.save_home({"global.conf": f"core.cache:database_path={tmp_path}"})
    client.run("list *")
    os.remove(os.path.join(client.cache_folder, "p", "cache.sqlite3.location"))
    client.run("list *", assert_error=True)
    assert "already contains a database" in client.out


@pytest.mark.parametrize("transfer", ["download", "restore"])
def test_database_path_transfer(tmp_path, transfer):
    source = TestClient(default_server_user=True)
    source.save_home({"global.conf": f"core.cache:database_path={tmp_path / 'source'}"})
    source.save({"conanfile.py": GenConanfile("pkg", "1.0").with_package_file("file.txt", "data")})
    source.run("create .")
    target = TestClient(servers=source.servers)
    target.save_home({"global.conf": f"core.cache:database_path={tmp_path / 'target'}"})
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
