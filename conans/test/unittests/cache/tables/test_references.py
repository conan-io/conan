import time

import pytest

from conan.cache._tables.references import References
from conan.utils.sqlite3 import Sqlite3MemoryMixin
from conans.model.ref import ConanFileReference


@pytest.fixture
def sqlite3memory():
    db = Sqlite3MemoryMixin()
    with db.connect() as conn:
        yield conn


def dump(conn, table):
    print("****")
    from io import StringIO
    output = StringIO()
    table.dump(conn, output)
    print(output.getvalue())
    print("****")


def test_save_and_retrieve(sqlite3memory):
    table = References()
    table.create_table(sqlite3memory)

    reference = 'name/version@user/channel#123456789'
    ref = ConanFileReference.loads(reference)
    ref_pk = table.save(sqlite3memory, ref)
    assert ref_pk == 1  # It is the first (and only) row in the table

    pk_ref = table.pk(sqlite3memory, ref)
    assert pk_ref == ref_pk

    ref = table.get(sqlite3memory, pk_ref)
    assert ref.full_str() == reference


def test_filter(sqlite3memory):
    table = References()
    table.create_table(sqlite3memory)

    ref1 = ConanFileReference.loads('name/v1@user/channel#123456789')
    ref2 = ConanFileReference.loads('name/v2@user/channel#123456789')
    ref3 = ConanFileReference.loads('other/v1@user/channel#123456789')
    ref4 = ConanFileReference.loads('other/v2@user/channel#123456789')

    table.save(sqlite3memory, ref1)
    table.save(sqlite3memory, ref2)
    table.save(sqlite3memory, ref3)
    table.save(sqlite3memory, ref4)

    name_refs = table.filter(sqlite3memory, '%name%', False)
    assert list(name_refs) == [ref1, ref2]

    v1_refs = table.filter(sqlite3memory, '%v1%', False)
    assert list(v1_refs) == [ref1, ref3]


def test_versions(sqlite3memory):
    table = References()
    table.create_table(sqlite3memory)

    ref1 = ConanFileReference.loads('name/v1@user/channel#123456789')
    ref2 = ConanFileReference.loads('name/v2@user/channel#123456789')
    ref3 = ConanFileReference.loads('other/v3@user/channel#123456789')
    ref4 = ConanFileReference.loads('other/v4@user/channel#123456789')

    table.save(sqlite3memory, ref1)
    table.save(sqlite3memory, ref2)
    table.save(sqlite3memory, ref3)
    table.save(sqlite3memory, ref4)

    name_versions = table.versions(sqlite3memory, ref1.name, False)
    assert list(name_versions) == [ref1, ref2]


def test_latest_rrev(sqlite3memory):
    table = References()
    table.create_table(sqlite3memory)

    ref2 = ConanFileReference.loads('name/v1@user/channel#222222222')
    ref3 = ConanFileReference.loads('name/v1@user/channel#111111111')

    table.save(sqlite3memory, ref2)
    time.sleep(1)
    table.save(sqlite3memory, ref3)

    latest = table.latest_rrev(sqlite3memory, ref2)
    assert latest == ref3
