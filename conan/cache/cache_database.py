from io import StringIO

from cache.exceptions import CacheDirectoryNotFound, CacheDirectoryAlreadyExists
from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin
from model.ref import ConanFileReference
from ._tables.folders import Folders
from ._tables.packages import Packages
from ._tables.references import References


class CacheDatabase:
    """ Abstracts the operations with the database and ensures they run sequentially """
    _references = References()
    _packages = Packages()
    _folders = Folders()

    def initialize(self, if_not_exists=True):
        with self.connect() as conn:
            self._references.create_table(conn, if_not_exists)
            self._packages.create_table(conn, self._references, if_not_exists)
            self._folders.create_table(conn, self._references, self._packages, if_not_exists)

    def dump(self, output: StringIO):
        with self.connect() as conn:
            output.write(f"\nReferences (table '{self._references.table_name}'):\n")
            self._references.dump(conn, output)

            output.write(f"\nPackages (table '{self._packages.table_name}'):\n")
            self._packages.dump(conn, output)

            output.write(f"\nFolders (table '{self._folders.table_name}'):\n")
            self._folders.dump(conn, output)

    """
    Functions related to references
    """

    def save_reference(self, ref: ConanFileReference, fail_if_exists: bool = False):
        with self.connect() as conn:
            self._references.save(conn, ref)
            # TODO: Implement fail_if_exists ==> integrity check in database

    def update_reference(self, old_ref: ConanFileReference, new_ref: ConanFileReference):
        """ Assigns a revision 'new_ref.revision' to the reference given by 'old_ref' """
        with self.connect() as conn:
            ref_pk = self._references.pk(conn, old_ref)
            self._references.update(conn, ref_pk, new_ref)

    def update_reference_directory(self, ref: ConanFileReference, path: str):
        with self.connect() as conn:
            self._folders.update_path_ref(conn, ref, path)

    def try_get_reference_directory(self, ref: ConanFileReference):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connect() as conn:
            return self._folders.get_path_ref(conn, ref)

    def create_reference_directory(self, ref: ConanFileReference, path: str) -> str:
        with self.connect() as conn:
            try:
                self._folders.get_path_ref(conn, ref)
            except CacheDirectoryNotFound:
                self._folders.save_ref(conn, ref, path)
            else:
                raise CacheDirectoryAlreadyExists(ref)

    def get_or_create_reference_directory(self, ref: ConanFileReference, path: str) -> str:
        with self.connect() as conn:
            try:
                return self._folders.get_path_ref(conn, ref)
            except Folders.DoesNotExist:
                self._folders.save_ref(conn, ref, path)
                return path


class CacheDatabaseSqlite3Memory(CacheDatabase, Sqlite3MemoryMixin):
    pass


class CacheDatabaseSqlite3Filesystem(CacheDatabase, Sqlite3FilesystemMixin):
    pass
