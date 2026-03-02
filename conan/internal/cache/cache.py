import hashlib
import os
import re
import shutil
import sqlite3
import uuid
from fnmatch import translate
from typing import List

from conan.api.model import PkgReference, RecipeReference
from conan.api.output import ConanOutput
from conan.errors import ConanException
from conan.internal.cache.concurrency_lock import ConcurrencyLock
from conan.internal.cache.conan_reference_layout import RecipeLayout, PackageLayout
from conan.internal.cache.db.cache_database import CacheDatabase
from conan.internal.errors import ConanReferenceAlreadyExistsInDB, ConanReferenceDoesNotExistInDB
from conan.internal.util.dates import revision_timestamp_now
from conan.internal.util.files import rmdir, renamedir, mkdir, atomic_replace


class CacheOperations:
    """
    Encapsulates atomic cache operations with proper locking.

    This class provides a clean separation between locking concerns and cache
    operations. All methods that modify the cache (DB + filesystem) are atomic
    and properly synchronized for multi-process/multi-thread access.

    The PkgCache class delegates to this class for operations that require
    locking, keeping locking logic centralized and testable.
    """

    def __init__(self, lock, db, base_folder, create_path_fn, full_path_fn):
        """
        Args:
            lock: ConcurrencyLock instance for synchronization
            db: CacheDatabase instance for DB operations
            base_folder: Base folder path for the cache
            create_path_fn: Function to create a path (relative_path, remove_contents) -> None
            full_path_fn: Function to get full path from relative path
        """
        self._lock = lock
        self._db = db
        self._base_folder = base_folder
        self._create_path = create_path_fn
        self._full_path = full_path_fn

    def create_recipe(self, ref, reference_path):
        """
        Atomically create a recipe entry in DB and filesystem.

        Args:
            ref: RecipeReference with revision set
            reference_path: Relative path for the recipe

        Raises:
            ConanReferenceAlreadyExistsInDB: If recipe already exists
        """
        with self._lock.recipe_lock(ref):
            self._db.create_recipe(reference_path, ref)
            self._create_path(reference_path, remove_contents=False)

    def create_package(self, pref, package_path):
        """
        Atomically create a package entry in DB and filesystem.

        Args:
            pref: PkgReference with revision set
            package_path: Relative path for the package

        Returns:
            True if created, False if already exists (another process created it)
        """
        with self._lock.package_lock(pref):
            try:
                self._db.create_package(package_path, pref, None)
            except ConanReferenceAlreadyExistsInDB:
                return False
            self._create_path(package_path, remove_contents=False)
            return True

    def remove_recipe(self, layout):
        """
        Atomically remove a recipe from filesystem and DB.

        This removes the recipe folder, all associated package folders,
        and cleans up corresponding DB entries.

        Args:
            layout: RecipeLayout to remove
        """
        with self._lock.recipe_lock(layout.reference):
            # First, get all package paths for this recipe before removing from DB
            ref = layout.reference
            pkg_refs_data = self._db.get_package_references_with_paths(ref)

            # Remove all package folders from disk
            for pkg_data in pkg_refs_data:
                pkg_path = pkg_data.get("path")
                if pkg_path:
                    full_pkg_path = self._full_path(pkg_path)
                    rmdir(full_pkg_path)

            # Remove the recipe folder
            layout.remove()

            # Remove recipe and all packages from DB
            self._db.remove_recipe(ref)

    def remove_package(self, layout):
        """
        Atomically remove a package from filesystem and DB.

        Args:
            layout: PackageLayout to remove
        """
        with self._lock.package_lock(layout.reference):
            layout.remove()
            self._db.remove_package(layout.reference)

    def assign_rrev(self, layout, new_path_relative, get_pkg_layout_fn):
        """
        Atomically assign a recipe revision by moving temp folder and updating DB.

        Called at export, once the exported recipe revision has been computed.

        Args:
            layout: RecipeLayout with the temporary folder
            new_path_relative: Destination relative path based on recipe revision
            get_pkg_layout_fn: Function to get PackageLayout for a pref (for existing packages)

        Note:
            This calls layout.relocate() to update the base folder path.
        """
        ref = layout.reference
        new_path_absolute = self._full_path(new_path_relative)

        with self._lock.recipe_lock(ref):
            if os.path.exists(new_path_absolute):
                # If the folder exists, export and export_sources
                # folders are already copied so we can remove the tmp ones
                rmdir(self._full_path(layout.base_folder))
            else:
                # Destination folder is empty, move all the tmp contents
                renamedir(self._full_path(layout.base_folder), new_path_absolute)

            layout.relocate(os.path.join(self._base_folder, new_path_relative))

            # Update the DB
            try:
                self._db.create_recipe(new_path_relative, ref)
            except ConanReferenceAlreadyExistsInDB:
                # This was exported before, making it latest again, update timestamp
                ref = layout.reference
                self._db.update_recipe_timestamp(ref)

    def assign_prev(self, layout, get_pkg_layout_fn):
        """
        Atomically assign a package revision by moving build folder and updating DB.

        Args:
            layout: PackageLayout with the build folder
            get_pkg_layout_fn: Function to get PackageLayout for a pref (for existing packages)

        Note:
            This calls layout.relocate() if package already exists.
        """
        pref = layout.reference
        build_id = layout.build_id

        with self._lock.package_lock(pref):
            relpath = os.path.relpath(layout.base_folder, self._base_folder)
            relpath = relpath.replace("\\", "/")  # Uniform for Windows and Linux
            try:
                self._db.create_package(relpath, pref, build_id)
            except ConanReferenceAlreadyExistsInDB:
                # There was a previous package folder for this same package reference (and prev)
                pkg_layout = get_pkg_layout_fn(pref)
                # We remove the old one and move the new one to the path of the previous one
                # this can be necessary in case of new metadata or build-folder due to build_id()
                pkg_layout.remove()
                shutil.move(layout.base_folder, pkg_layout.base_folder)  # clean temp build
                layout.relocate(pkg_layout.base_folder)  # reuse existing one
                # Path is unchanged (same pref hash), only update timestamp and build_id
                self._db.update_package_timestamp(pref, build_id=build_id)

    def source_lock(self, ref):
        """
        Get a context manager for source operations requiring locking.

        This is used by external callers (like BinaryInstaller) that need to
        protect source folder operations.

        Args:
            ref: RecipeReference to lock source operations for

        Returns:
            Context manager that holds the source lock
        """
        return self._lock.source_lock(ref)


class PkgCache:
    """ Class to represent the recipes and packages storage in disk
    """

    def __init__(self, cache_folder, global_conf):
        # paths
        self._store_folder = global_conf.get("core.cache:storage_path") or \
                             os.path.join(cache_folder, "p")

        try:
            mkdir(self._store_folder)
            db_filename = os.path.join(self._store_folder, 'cache.sqlite3')
            self._base_folder = os.path.abspath(self._store_folder)
            self._db = CacheDatabase(filename=db_filename)
            self._lock = ConcurrencyLock(self._store_folder)
            # Create the operations layer that encapsulates locking + DB + filesystem
            self._ops = CacheOperations(
                lock=self._lock,
                db=self._db,
                base_folder=self._base_folder,
                create_path_fn=self._create_path,
                full_path_fn=self._full_path
            )
        except Exception as e:
            raise ConanException(f"Couldn't initialize storage in {self._store_folder}: {e}")

    @property
    def store(self):
        return self._base_folder

    def source_operation(self, ref):
        """
        Context manager for source operations requiring locking.

        Use this when performing source folder operations (source() method,
        exports_sources retrieval) to prevent race conditions.

        Args:
            ref: RecipeReference to lock source operations for

        Returns:
            Context manager that holds the source lock

        Example:
            with cache.source_operation(ref):
                # Perform source operations safely
                retrieve_exports_sources(...)
                config_source(...)
        """
        return self._ops.source_lock(ref)

    def package_lock(self, pref):
        """
        Context manager for package build operations requiring locking.

        Use this when performing package-specific operations (source copying,
        build operations, packaging) to prevent race conditions when multiple
        processes build the same package simultaneously.

        Args:
            pref: PkgReference to lock package operations for

        Returns:
            Context manager that holds the package lock

        Example:
            with cache.package_lock(pref):
                # Perform package operations safely
                copy_sources(...)
                build(...)
                package(...)
        """
        return self._lock.package_lock(pref)

    def recipe_lock(self, ref):
        """
        Context manager for recipe update operations requiring locking.

        Use this when performing recipe-specific operations (downloading,
        timestamp updates, checking for updates) to prevent race conditions
        when multiple processes update/download the same recipe simultaneously.

        Args:
            ref: RecipeReference to lock recipe operations for

        Returns:
            Context manager that holds the recipe lock

        Example:
            with cache.recipe_lock(ref):
                # Check for updates and download safely
                if needs_update():
                    download_recipe(...)
                    update_timestamp(...)
        """
        return self._lock.recipe_lock(ref)

    @property
    def temp_folder(self):
        """ temporary folder where Conan puts exports and packages before the final revision
        is computed"""
        # TODO: Improve the path definitions, this is very hardcoded
        return os.path.join(self._base_folder, "t")

    @property
    def builds_folder(self):
        return os.path.join(self._base_folder, "b")

    def _create_path(self, relative_path, remove_contents=True):
        path = self._full_path(relative_path)
        if os.path.exists(path) and remove_contents:
            rmdir(path)
        os.makedirs(path, exist_ok=True)

    def _full_path(self, relative_path):
        # This one is used only for rmdir and mkdir operations, not returned to user
        # or stored in DB
        path = os.path.realpath(os.path.join(self._base_folder, relative_path))
        return path

    @staticmethod
    def _short_hash_path(h):
        """:param h: Unicode text to reduce"""
        h = h.encode("utf-8")
        md = hashlib.sha256()
        md.update(h)
        sha_bytes = md.hexdigest()
        # len based on: https://github.com/conan-io/conan/pull/9595#issuecomment-918976451
        # Reduce length in 3 characters 16 - 3 = 13
        return sha_bytes[0:13]

    @staticmethod
    def _get_path(ref):
        return ref.name[:5] + PkgCache._short_hash_path(ref.repr_notime())

    @staticmethod
    def _get_path_pref(pref):
        return pref.ref.name[:5] + PkgCache._short_hash_path(pref.repr_notime())

    def create_export_recipe_layout(self, ref: RecipeReference):
        """  This is a temporary layout while exporting a new recipe, because the revision is not
        computed until later. The entry is not added to DB, just a temp folder is created

        This temporary export folder will be moved to permanent when revision is computed by the
        assign_rrev() method
        """
        assert ref.revision is None, "Recipe revision should be None"
        assert ref.timestamp is None
        # Use UUID to ensure unique temp folder for concurrent exports of the same ref
        random_id = str(uuid.uuid4())
        h = ref.name[:5] + PkgCache._short_hash_path(ref.repr_notime() + random_id)
        reference_path = os.path.join("t", h)
        self._create_path(reference_path)
        return RecipeLayout(ref, os.path.join(self._base_folder, reference_path), self._lock)

    def create_build_pkg_layout(self, pref: PkgReference):
        # Temporary layout to build a new package, when we don't know the package revision yet
        assert pref.ref.revision, "Recipe revision must be known to get or create the package layout"
        assert pref.package_id, "Package id must be known to get or create the package layout"
        assert pref.revision is None, "Package revision should be None"
        assert pref.timestamp is None

        random_id = str(uuid.uuid4())
        h = pref.ref.name[:5] + PkgCache._short_hash_path(pref.repr_notime() + random_id)
        package_path = os.path.join("b", h)
        self._create_path(package_path)
        return PackageLayout(pref, os.path.join(self._base_folder, package_path), self._lock)

    def recipe_layout(self, ref: RecipeReference):
        """ the revision must exists, the folder must exist
        The regular graph building will use this method if the revision is defined, like
        when using lockfiles or explicit, or recipe_layout_latest() if not, to do one single DB
        query
        """
        assert ref.revision is not None
        ref_data = self._db.get_recipe(ref)
        ref_path = ref_data.get("path")
        ref = ref_data.get("ref")  # new revision with timestamp
        return RecipeLayout(ref, os.path.join(self._base_folder, ref_path), self._lock)

    def recipe_layout_latest(self, ref: RecipeReference):
        """ the revision must be None, the folder must exist
        This method was added so the ConanProxy used to resolve the dependency graph
        avoid doing 2 DB calls when the revision is not defined
        """
        assert ref.revision is None
        ref_data = self._db.get_latest_recipe(ref)
        ref_path = ref_data.get("path")
        ref = ref_data.get("ref")  # new revision with timestamp
        return RecipeLayout(ref, os.path.join(self._base_folder, ref_path), self._lock)

    def get_latest_recipe_revision(self, ref: RecipeReference) -> RecipeReference:
        assert ref.revision is None
        ref_data = self._db.get_latest_recipe(ref)
        return ref_data.get("ref")

    def get_recipe_revisions(self, ref: RecipeReference):
        # For listing multiple revisions only
        assert ref.revision is None
        return self._db.get_recipe_revisions_references(ref)

    def pkg_layout(self, pref: PkgReference):
        """ the revision must exists, the folder must exist
        No longer used by GraphBinariesAnalyzer
        """
        assert pref.ref.revision, "Recipe revision must be known to get the package layout"
        assert pref.package_id, "Package id must be known to get the package layout"
        assert pref.revision, "Package revision must be known to get the package layout"
        pref_data = self._db.try_get_package(pref)
        pref_path = pref_data.get("path")
        # we use abspath to convert cache forward slash in Windows to backslash
        return PackageLayout(pref, os.path.abspath(os.path.join(self._base_folder, pref_path)),
                           self._lock)

    def pkg_layout_latest(self, pref: PkgReference):
        """
        GraphBinariesAnalyzer will call this method to avoid doing 2 DB calls, previously
        it was using pkg_layout() after a get_latest_package_revision()
        """
        assert pref.ref.revision, "Recipe revision must be known to get the package layout"
        assert pref.package_id, "Package id must be known to get the package layout"
        assert pref.revision is None

        pref_data = self._db.get_latest_package_reference_data(pref)
        if pref_data is None:
            return None
        pref_path = pref_data.get("path")
        pref = pref_data.get("pref")  # new revision with timestamp
        # we use abspath to convert cache forward slash in Windows to backslash
        base_path = os.path.abspath(os.path.join(self._base_folder, pref_path))
        # Verify the package folder actually exists on disk
        # This handles the case where a previous download was interrupted
        pkg_folder = os.path.join(base_path, "p")
        if not os.path.isdir(pkg_folder):
            # DB entry exists but folder doesn't - treat as missing
            return None
        return PackageLayout(pref, base_path, self._lock)

    def create_ref_layout(self, ref: RecipeReference):
        """ called exclusively by:
        - RemoteManager.get_recipe()
        - cache restore

        Raises:
            ConanReferenceAlreadyExistsInDB: If recipe already exists (caught by proxy for updates)
        """
        assert ref.revision, "Recipe revision must be known to create the package layout"
        reference_path = self._get_path(ref)
        self._ops.create_recipe(ref, reference_path)
        return RecipeLayout(ref, os.path.join(self._base_folder, reference_path), self._lock)

    def create_pkg_layout(self, pref: PkgReference):
        """ called by:
         - RemoteManager.get_package()
         - cache restore
        Returns None if the package already exists (another process created it)
        """
        assert pref.ref.revision, "Recipe revision must be known to create the package layout"
        assert pref.package_id, "Package id must be known to create the package layout"
        assert pref.revision, "Package revision should be known to create the package layout"
        package_path = self._get_path_pref(pref)
        if not self._ops.create_package(pref, package_path):
            # Another process already created this package, skip
            return None
        return PackageLayout(pref, os.path.join(self._base_folder, package_path), self._lock)

    def get_random_path(self):
        random_id = str(uuid.uuid4())
        # d=downloading area. Using short hashes to avoid lengthy paths with hyphens
        return os.path.join(self._base_folder, "d", self._short_hash_path(random_id))

    def create_atomic_pkg_layout(self, pref: PkgReference, current_folder):
        """ called by:
         - RemoteManager.get_package()
        """
        assert pref.ref.revision, "Recipe revision must be known to create the package layout"
        assert pref.package_id, "Package id must be known to create the package layout"
        assert pref.revision, "Package revision should be known to create the package layout"
        package_path = self._get_path_pref(pref)
        path = self._full_path(package_path)

        # Hold package lock during the entire operation
        # This ensures waiting processes don't return until both DB and folder are ready
        # Note: We must release lock quickly to avoid blocking other operations like LRU updates
        with self.package_lock(pref):
            # Create DB entry first, BEFORE moving folder.
            # If another process already registered this package, this raises
            # ConanReferenceAlreadyExistsInDB which the caller handles.
            self._db.create_package(package_path, pref, None)

            # If the destination folder already exists it must be an orphaned directory
            # from a previous interrupted download (the DB had no entry, proven above).
            # os.replace() on Linux fails with ENOTEMPTY when the destination directory
            # is non-empty, so remove it while we hold the lock before the rename.
            if os.path.exists(path):
                rmdir(path)

            try:
                # atomic_replace is atomic at filesystem level
                # If it fails, clean up the DB entry we just created
                atomic_replace(current_folder, path, f"{pref.repr_notime()} package")
            except Exception:
                # atomic_replace failed, remove the DB entry we just created
                try:
                    self._db.remove_package(pref)
                except Exception:
                    pass  # Best effort cleanup
                raise

    def update_recipe_timestamp(self, ref: RecipeReference):
        """ when the recipe already exists in cache, but we get a new timestamp from a server
        that would affect its order in our cache """
        assert ref.revision
        assert ref.timestamp
        self._db.update_recipe_timestamp(ref)

    def search_recipes(self, pattern=None, ignorecase=True):
        # Conan references in main storage
        if pattern:
            if isinstance(pattern, RecipeReference):
                pattern = repr(pattern)
            pattern = translate(pattern)
            pattern = re.compile(pattern, re.IGNORECASE if ignorecase else 0)

        return self._db.list_references(pattern)

    def exists_prev(self, pref):
        # Used just by download to skip downloads if prev already exists in cache
        # Also verify the package folder actually exists on disk
        if not self._db.exists_prev(pref):
            return False
        # DB entry exists, verify the folder also exists
        # This handles the case where a previous download was interrupted after
        # creating the DB entry but before completing the folder creation
        try:
            pref_data = self._db.try_get_package(pref)
            pref_path = pref_data.get("path")
            pkg_folder = os.path.join(self._base_folder, pref_path, "p")
            if os.path.isdir(pkg_folder):
                return True
            # Folder doesn't exist, this is an orphaned DB entry
            # Don't clean it up here (might cause race conditions), just return False
            # so the package gets re-downloaded
            return False
        except ConanReferenceDoesNotExistInDB as e:
            # Expected race condition - another process deleted the entry between
            # exists_prev check and try_get_package call
            ConanOutput().debug(f"Package entry removed during check for {pref!r}: {e}")
            return False
        except sqlite3.OperationalError as e:
            # Transient database issues (locked, busy, etc.) - expected in concurrent scenarios
            ConanOutput().debug(f"Database busy checking package {pref!r}: {e}")
            return False
        except sqlite3.Error as e:
            # Unexpected database error (corruption, programming error, etc.)
            # Log at warning level as this indicates a serious issue
            ConanOutput().warning(f"Database error checking package {pref!r}: {e}")
            return False

    def get_latest_package_revision(self, pref: PkgReference) -> PkgReference:
        # This is no longer needed by the Graph resolution functionality, only by ListAPI
        # its usage in graph resolution has been replaced by a single call to pkg_layout_latest()
        return self._db.get_latest_package_reference(pref)

    def get_package_references(self, ref: RecipeReference,
                               only_latest_prev=True) -> List[PkgReference]:
        """Get the latest package references"""
        return self._db.get_package_references(ref, only_latest_prev)

    def get_package_revisions(self, pref: PkgReference) -> List[PkgReference]:
        return self._db.get_package_revisions_references(pref)

    def get_matching_build_id(self, ref, build_id):
        return self._db.get_matching_build_id(ref, build_id)

    def remove_recipe_layout(self, layout: RecipeLayout):
        self._ops.remove_recipe(layout)

    def remove_package_layout(self, layout: PackageLayout):
        self._ops.remove_package(layout)

    def remove_build_id(self, pref):
        self._db.remove_build_id(pref)

    def assign_prev(self, layout: PackageLayout):
        pref = layout.reference
        pref.timestamp = revision_timestamp_now()
        self._ops.assign_prev(layout, self.pkg_layout)

    def assign_rrev(self, layout: RecipeLayout):
        """ called at export, once the exported recipe revision has been computed, it
        can register for the first time the new RecipeReference"""
        ref = layout.reference
        assert ref.revision is not None, "Revision must exist after export"
        assert ref.timestamp is None, "Timestamp no defined yet"
        ref.timestamp = revision_timestamp_now()

        # This is the destination path for the temporary created export and export_sources folders
        # with the hash created based on the recipe revision
        new_path_relative = self._get_path(ref)
        self._ops.assign_rrev(layout, new_path_relative, self.pkg_layout)

    def get_recipe_lru(self, ref):
        return self._db.get_recipe_lru(ref)

    def update_recipes_lru(self, refs):
        self._db.update_recipes_lru(refs)

    def get_package_lru(self, pref):
        return self._db.get_package_lru(pref)

    def update_packages_lru(self, prefs):
        self._db.update_packages_lru(prefs)

    def path_to_ref(self, path):
        try:
            path = os.path.relpath(path, self._base_folder)
            path = path.replace("\\", "/")  # Uniform for Windows and Linux
        except ValueError:
            raise ConanException(f"Invalid path: {path}")
        return self._db.path_to_ref(path)
