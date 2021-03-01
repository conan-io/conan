import pytest

from conan.cache._tables.folders import Folders, ConanFolders
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


def test_save_and_retrieve_ref(sqlite3memory):
    references_table = References()
    references_table.create_table(sqlite3memory)
    packages_table = Packages()
    packages_table.create_table(sqlite3memory, references_table, True)
    table = Folders()
    table.create_table(sqlite3memory, references_table, packages_table, True)

    ref1 = ConanFileReference.loads('name/version@user/channel#111111')
    ref2 = ConanFileReference.loads('name/version@user/channel#222222')
    references_table.save(sqlite3memory, ref1)
    references_table.save(sqlite3memory, ref2)

    path1 = 'path/for/reference/1'
    path2 = 'path/for/reference/2'
    table.save_ref(sqlite3memory, ref1, path1)
    table.save_ref(sqlite3memory, ref2, path2)

    assert path1 == table.get_path_ref(sqlite3memory, ref1)
    assert path2 == table.get_path_ref(sqlite3memory, ref2)


def test_save_and_retrieve_pref(sqlite3memory):
    references_table = References()
    references_table.create_table(sqlite3memory)
    packages_table = Packages()
    packages_table.create_table(sqlite3memory, references_table, True)
    table = Folders()
    table.create_table(sqlite3memory, references_table, packages_table, True)

    pref1 = PackageReference.loads('name/version@user/channel#111111:123456789#9999')
    references_table.save(sqlite3memory, pref1.ref)
    packages_table.save(sqlite3memory, pref1)

    path1 = 'path/for/pref1/build'
    path2 = 'path/for/pref1/package'
    table.save_pref(sqlite3memory, pref1, path1, ConanFolders.PKG_BUILD)
    table.save_pref(sqlite3memory, pref1, path2, ConanFolders.PKG_PACKAGE)

    assert path1 == table.get_path_pref(sqlite3memory, pref1, ConanFolders.PKG_BUILD)
    assert path2 == table.get_path_pref(sqlite3memory, pref1, ConanFolders.PKG_PACKAGE)
