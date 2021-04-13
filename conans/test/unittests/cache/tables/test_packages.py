import os
import tempfile
import time

import pytest

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


def test_save_and_retrieve(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    table = Packages()
    table.create_table(sqlite3_database, references_table, True)

    package_reference = 'name/version@user/channel#123456789:11111111111#987654321'
    pref = PackageReference.loads(package_reference)
    references_table.save(sqlite3_database, pref.ref)
    pref_pk = table.save(sqlite3_database, pref)
    assert pref_pk == 1  # It is the first (and only) row in the table

    pk_pref = table.pk(sqlite3_database, pref)
    assert pk_pref == pref_pk

    pref = table.get(sqlite3_database, pk_pref)
    assert pref.full_str() == package_reference


def test_filter(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    table = Packages()
    table.create_table(sqlite3_database, references_table, True)

    ref1 = ConanFileReference.loads('name/v1@user/channel#123456789')
    ref2 = ConanFileReference.loads('other/v1@user/channel#132456798')
    references_table.save(sqlite3_database, ref1)
    references_table.save(sqlite3_database, ref2)

    pref1 = PackageReference.loads(f'{ref1.full_str()}:111111111#999')
    pref2 = PackageReference.loads(f'{ref1.full_str()}:111111111#888')
    pref3 = PackageReference.loads(f'{ref1.full_str()}:222222222#999')
    prefn = PackageReference.loads(f'{ref2.full_str()}:111111111#999')

    table.save(sqlite3_database, pref1)
    table.save(sqlite3_database, pref2)
    table.save(sqlite3_database, pref3)
    table.save(sqlite3_database, prefn)

    prefs = table.filter(sqlite3_database, ref1)
    assert sorted(list(prefs)) == [pref2, pref1, pref3]


def test_latest_prev(sqlite3_database):
    references_table = References()
    references_table.create_table(sqlite3_database)
    table = Packages()
    table.create_table(sqlite3_database, references_table, True)

    ref = ConanFileReference.loads('name/v1@user/channel#222222222')
    references_table.save(sqlite3_database, ref)
    pref1 = PackageReference.loads(f'{ref.full_str()}:111111111#999')
    pref2 = PackageReference.loads(f'{ref.full_str()}:111111111#888')

    table.save(sqlite3_database, pref1)
    time.sleep(1)
    table.save(sqlite3_database, pref2)

    latest = table.latest_prev(sqlite3_database, pref1)
    assert latest == pref2
