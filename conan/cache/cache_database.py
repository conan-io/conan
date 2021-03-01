from io import StringIO

from _tables.folders import Folders
from _tables.packages import Packages
from _tables.references import References
from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin
from model.ref import ConanFileReference


class CacheDatabase:
    """ Abstracts the operations with the database and ensures they run sequentially """
    references = References()
    packages = Packages()
    folders = Folders()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def initialize(self, if_not_exists=True):
        with self.connect() as conn:
            self.references.create_table(conn, if_not_exists)
            self.packages.create_table(conn, self.references, if_not_exists)
            self.folders.create_table(conn, if_not_exists)

    def dump(self, output: StringIO):
        with self.connect() as conn:
            output.write(f"\nReferences (table '{self.references.table_name}'):\n")
            self.references.dump(conn, output)

            output.write(f"\nPackages (table '{self.packages.table_name}'):\n")
            self.packages.dump(conn, output)

            output.write(f"\nFolders (table '{self.folders.table_name}'):\n")
            self.folders.dump(conn, output)

    def try_get_reference_directory(self, item: ConanFileReference):
        """ Returns the directory where the given reference is stored """
        with self.connect() as conn:
            pk = self.references.get(item)


class CacheDatabaseSqlite3Memory(CacheDatabase, Sqlite3MemoryMixin):
    pass


class CacheDatabaseSqlite3Filesystem(CacheDatabase, Sqlite3FilesystemMixin):
    pass
