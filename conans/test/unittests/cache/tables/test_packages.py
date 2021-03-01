import time

import pytest

from conan.cache._tables.packages import Packages
from conan.cache._tables.references import References
from conan.utils.sqlite3 import Sqlite3MemoryMixin
from conans.model.ref import ConanFileReference, PackageReference


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
    references_table = References()
    references_table.create_table(sqlite3memory)
    table = Packages()
    table.create_table(sqlite3memory, references_table, True)

    package_reference = 'name/version@user/channel#123456789:11111111111#987654321'
    pref = PackageReference.loads(package_reference)
    references_table.save(sqlite3memory, pref.ref)
    pref_pk = table.save(sqlite3memory, pref)
    assert pref_pk == 1  # It is the first (and only) row in the table

    pk_pref = table.pk(sqlite3memory, pref)
    assert pk_pref == pref_pk

    pref = table.get(sqlite3memory, pk_pref)
    assert pref.full_str() == package_reference
