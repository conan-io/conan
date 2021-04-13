import os
import tempfile
import time

import pytest

from conan.cache._tables.references import References
from conan.cache.cache_database import CacheDatabase
from conans.model.ref import ConanFileReference
from conans.test import CONAN_TEST_FOLDER


@pytest.fixture
def sqlite3_database():
    with tempfile.TemporaryDirectory(suffix='conans', dir=CONAN_TEST_FOLDER) as tmpdirname:
        db_filename = os.path.join(tmpdirname, 'cache.sqlite3')
        database = CacheDatabase(db_filename)
        with database.connect() as conn:
            yield conn


def test_save_and_retrieve(sqlite3_database):
    table = References()
    table.create_table(sqlite3_database)

    reference = 'name/version@user/channel#123456789'
    ref = ConanFileReference.loads(reference)
    ref_pk = table.save(sqlite3_database, ref)
    assert ref_pk == 1  # It is the first (and only) row in the table

    pk_ref = table.pk(sqlite3_database, ref)
    assert pk_ref == ref_pk

    ref = table.get(sqlite3_database, pk_ref)
    assert ref.full_str() == reference


def test_filter(sqlite3_database):
    table = References()
    table.create_table(sqlite3_database)

    ref1 = ConanFileReference.loads('name/v1@user/channel#123456789')
    ref2 = ConanFileReference.loads('name/v2@user/channel#123456789')
    ref3 = ConanFileReference.loads('other/v1@user/channel#123456789')
    ref4 = ConanFileReference.loads('other/v2@user/channel#123456789')

    table.save(sqlite3_database, ref1)
    table.save(sqlite3_database, ref2)
    table.save(sqlite3_database, ref3)
    table.save(sqlite3_database, ref4)

    name_refs = table.filter(sqlite3_database, '%name%', False)
    assert list(name_refs) == [ref1, ref2]

    v1_refs = table.filter(sqlite3_database, '%v1%', False)
    assert list(v1_refs) == [ref1, ref3]


def test_versions(sqlite3_database):
    table = References()
    table.create_table(sqlite3_database)

    ref1 = ConanFileReference.loads('name/v1@user/channel#123456789')
    ref2 = ConanFileReference.loads('name/v2@user/channel#123456789')
    ref3 = ConanFileReference.loads('other/v3@user/channel#123456789')
    ref4 = ConanFileReference.loads('other/v4@user/channel#123456789')

    table.save(sqlite3_database, ref1)
    table.save(sqlite3_database, ref2)
    table.save(sqlite3_database, ref3)
    table.save(sqlite3_database, ref4)

    name_versions = table.versions(sqlite3_database, ref1.name, False)
    assert list(name_versions) == [ref1, ref2]


def test_latest_rrev(sqlite3_database):
    table = References()
    table.create_table(sqlite3_database)

    ref2 = ConanFileReference.loads('name/v1@user/channel#222222222')
    ref3 = ConanFileReference.loads('name/v1@user/channel#111111111')

    table.save(sqlite3_database, ref2)
    time.sleep(1)
    table.save(sqlite3_database, ref3)

    latest = table.latest_rrev(sqlite3_database, ref2)
    assert latest == ref3
