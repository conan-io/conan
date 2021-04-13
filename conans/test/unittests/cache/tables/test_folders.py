import os
import tempfile
import time

import pytest

from conan.cache._tables.folders import Folders, ConanFolders
from conan.cache._tables.packages import Packages
from conan.cache._tables.references import References
from conan.cache.cache_database import CacheDatabase
from conans.model.ref import ConanFileReference, PackageReference
from conans.test import CONAN_TEST_FOLDER


@pytest.fixture
def sqlite3_database():
    with tempfile.TemporaryDirectory(suffix='conans', dir=CONAN_TEST_FOLDER) as tmpdirname:
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        database = CacheDatabase(db_filename)
        with database.connect() as conn:
            yield conn


def test_save_and_retrieve_ref(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    packages_table = Packages()
    packages_table.create_table(sqlite3_database, references_table, True)
    table = Folders()
    table.create_table(sqlite3_database, references_table, packages_table, True)

    ref1 = ConanFileReference.loads('name/version@user/channel#111111')
    ref2 = ConanFileReference.loads('name/version@user/channel#222222')
    references_table.save(sqlite3_database, ref1)
    references_table.save(sqlite3_database, ref2)

    path1 = 'path/for/reference/1'
    path2 = 'path/for/reference/2'
    table.save_ref(sqlite3_database, ref1, path1)
    table.save_ref(sqlite3_database, ref2, path2)

    assert path1 == table.get_path_ref(sqlite3_database, ref1)
    assert path2 == table.get_path_ref(sqlite3_database, ref2)


def test_save_and_retrieve_pref(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    packages_table = Packages()
    packages_table.create_table(sqlite3_database, references_table, True)
    table = Folders()
    table.create_table(sqlite3_database, references_table, packages_table, True)

    pref1 = PackageReference.loads('name/version@user/channel#111111:123456789#9999')
    references_table.save(sqlite3_database, pref1.ref)
    packages_table.save(sqlite3_database, pref1)
    table.save_ref(sqlite3_database, pref1.ref, 'path/to/ref')

    path1 = 'path/for/pref1/build'
    path2 = 'path/for/pref1/package'
    table.save_pref(sqlite3_database, pref1, path1, ConanFolders.PKG_BUILD)
    table.save_pref(sqlite3_database, pref1, path2, ConanFolders.PKG_PACKAGE)

    assert path1 == table.get_path_pref(sqlite3_database, pref1, ConanFolders.PKG_BUILD)
    assert path2 == table.get_path_pref(sqlite3_database, pref1, ConanFolders.PKG_PACKAGE)


def test_lru_ref(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    packages_table = Packages()
    packages_table.create_table(sqlite3_database, references_table, True)
    table = Folders()
    table.create_table(sqlite3_database, references_table, packages_table, True)

    ref1 = ConanFileReference.loads('name/version@user/channel#111111')
    ref2 = ConanFileReference.loads('name/version@user/channel#222222')
    references_table.save(sqlite3_database, ref1)
    references_table.save(sqlite3_database, ref2)

    path1 = 'path/for/reference/1'
    path2 = 'path/for/reference/2'
    table.save_ref(sqlite3_database, ref1, path1)
    table.save_ref(sqlite3_database, ref2, path2)

    time.sleep(1)
    now = int(time.time())

    assert [ref1, ref2] == list(table.get_lru_ref(sqlite3_database, now))

    # Touch one of them and get LRU again
    table.touch_ref(sqlite3_database, ref1)
    assert [ref2] == list(table.get_lru_ref(sqlite3_database, now))


def test_lru_pref(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    packages_table = Packages()
    packages_table.create_table(sqlite3_database, references_table, True)
    table = Folders()
    table.create_table(sqlite3_database, references_table, packages_table, True)

    pref1 = PackageReference.loads('name/version@user/channel#111111:123456789#9999')
    references_table.save(sqlite3_database, pref1.ref)
    packages_table.save(sqlite3_database, pref1)
    table.save_ref(sqlite3_database, pref1.ref, 'path/for/recipe')

    path1 = 'path/for/pref1/build'
    path2 = 'path/for/pref1/package'
    table.save_pref(sqlite3_database, pref1, path1, ConanFolders.PKG_BUILD)
    table.save_pref(sqlite3_database, pref1, path2, ConanFolders.PKG_PACKAGE)

    time.sleep(1)
    now = int(time.time())

    assert [pref1.ref, ] == list(table.get_lru_ref(sqlite3_database, now))
    assert [pref1] == list(table.get_lru_pref(sqlite3_database, now))

    # Touching a ref only updates the ref implies touching the ref
    table.touch_ref(sqlite3_database, pref1.ref)
    assert [] == list(table.get_lru_ref(sqlite3_database, now))
    assert [pref1] == list(table.get_lru_pref(sqlite3_database, now))

    # Touching the pref updates both
    table.touch_pref(sqlite3_database, pref1)
    assert [] == list(table.get_lru_ref(sqlite3_database, now))
    assert [] == list(table.get_lru_pref(sqlite3_database, now))
