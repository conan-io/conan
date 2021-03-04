import sqlite3
from io import StringIO
from typing import Tuple, Iterator

from conan.utils.sqlite3 import Sqlite3MemoryMixin, Sqlite3FilesystemMixin
from conans.model.ref import ConanFileReference, PackageReference
from ._tables.folders import Folders, ConanFolders
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

    def list_references(self, only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        with self.connect() as conn:
            for it in self._references.all(conn, only_latest_rrev):
                yield it

    def search_references(self, pattern: str,
                          only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        with self.connect() as conn:
            for it in self._references.filter(conn, pattern, only_latest_rrev):
                yield it

    def list_reference_versions(self, name: str,
                                only_latest_rrev: bool) -> Iterator[ConanFileReference]:
        with self.connect() as conn:
            for it in self._references.versions(conn, name, only_latest_rrev):
                yield it

    def update_reference(self, old_ref: ConanFileReference, new_ref: ConanFileReference):
        """ Assigns a revision 'new_ref.revision' to the reference given by 'old_ref' """
        with self.connect() as conn:
            ref_pk = self._references.pk(conn, old_ref)
            try:
                self._references.update(conn, ref_pk, new_ref)
            except sqlite3.IntegrityError:
                raise References.AlreadyExist(f"Reference '{new_ref.full_str()}' already exists")

    def update_reference_directory(self, ref: ConanFileReference, path: str):
        with self.connect() as conn:
            self._folders.update_path_ref(conn, ref, path)

    def try_get_reference_directory(self, ref: ConanFileReference):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connect() as conn:
            return self._folders.get_path_ref(conn, ref)

    def get_or_create_reference(self, ref: ConanFileReference, path: str) -> Tuple[str, bool]:
        """ Returns the path for the given reference. If the reference doesn't exist in the
            database, it will create the entry for the reference using the path given as argument.
        """
        with self.connect() as conn:
            try:
                return self._folders.get_path_ref(conn, ref), False
            except References.DoesNotExist:
                self._references.save(conn, ref)
                self._folders.save_ref(conn, ref, path)
                return path, True

    """
    Functions related to package references
    """

    def list_package_references(self, ref: ConanFileReference,
                                only_latest_prev: bool) -> Iterator[PackageReference]:
        with self.connect() as conn:
            for it in self._packages.filter(conn, ref, only_latest_prev):
                yield it

    def search_package_references(self, ref: ConanFileReference, package_id: str,
                                  only_latest_prev: bool) -> Iterator[PackageReference]:
        with self.connect() as conn:
            for it in self._packages.search(conn, ref, package_id, only_latest_prev):
                yield it

    def update_package_reference(self, old_pref: PackageReference, new_pref: PackageReference):
        """ Assigns a revision 'new_ref.revision' to the reference given by 'old_ref' """
        with self.connect() as conn:
            pref_pk = self._packages.pk(conn, old_pref)
            try:
                self._packages.update(conn, pref_pk, new_pref)
            except sqlite3.IntegrityError:
                raise Packages.AlreadyExist(f"Package '{new_pref.full_str()}' already exists")

    def update_package_reference_directory(self, pref: PackageReference, path: str,
                                           folder: ConanFolders):
        with self.connect() as conn:
            self._folders.update_path_pref(conn, pref, path, folder)

    def try_get_package_reference_directory(self, pref: PackageReference, folder: ConanFolders):
        """ Returns the directory where the given reference is stored (or fails) """
        with self.connect() as conn:
            return self._folders.get_path_pref(conn, pref, folder)

    def get_or_create_package_reference_directory(self, pref: PackageReference, path: str,
                                                  folder: ConanFolders) -> str:
        with self.connect() as conn:
            try:
                return self._folders.get_path_pref(conn, pref, folder)
            except Folders.DoesNotExist:
                self._folders.save_pref(conn, pref, path, folder)
                return path

    def get_or_create_package(self, pref: PackageReference, path: str,
                              folder: ConanFolders) -> Tuple[str, bool]:
        """ Returns the path for the given package. The corresponding reference must exist.
            If the package doesn't exist in the database, it will create the entry for the package
            using the path given as argument.
        """
        with self.connect() as conn:
            try:
                return self._folders.get_path_pref(conn, pref, folder), False
            except Packages.DoesNotExist:
                self._packages.save(conn, pref)
                self._folders.save_pref(conn, pref, path, folder)
                return path, True


class CacheDatabaseSqlite3Memory(CacheDatabase, Sqlite3MemoryMixin):
    pass


class CacheDatabaseSqlite3Filesystem(CacheDatabase, Sqlite3FilesystemMixin):
    pass
