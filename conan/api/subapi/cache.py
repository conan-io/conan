import json
import os
import shutil
import tarfile
import tempfile

from conan.api.model import PackagesList
from conan.api.output import ConanOutput
from conan.internal.api.uploader import compress_files, get_compress_level
from conan.internal.cache.cache import PkgCache
from conan.internal.cache.conan_reference_layout import (EXPORT_SRC_FOLDER, EXPORT_FOLDER,
                                                         SRC_FOLDER, METADATA,
                                                         DOWNLOAD_EXPORT_FOLDER)
from conan.internal.cache.home_paths import HomePaths
from conan.internal.cache.integrity_check import IntegrityChecker
from conan.internal.paths import COMPRESSIONS
from conan.internal.rest.download_cache import DownloadCache
from conan.errors import ConanException
from conan.api.model import PkgReference
from conan.api.model import RecipeReference
from conan.internal.util.dates import revision_timestamp_now
from conan.internal.util.files import rmdir, mkdir, remove, save


class CacheAPI:
    """ This CacheAPI is used to interact with the packages storage cache

    Note that the Conan packages cache is exclusively **read-only** for user code. Only Conan
    can write or modify the folders and files in the Conan cache. In general, when a method
    returns a folder, it is mostly for debugging purposes and read-only access, but never to
    modify the contents of the cache.
    """

    def __init__(self, conan_api, api_helpers):
        self._conan_api = conan_api
        self._api_helpers = api_helpers

    def export_path(self, ref: RecipeReference):
        """Returns the path of the recipe conanfile and exported files in the Conan cache

        This folder is exclusively for **read-only** access, typically for debugging purposes,
        it is completely forbidden to modify any of its contents.

        :param ref: RecipeReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """

        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        ref = _resolve_latest_ref(cache, ref)
        ref_layout = cache.recipe_layout(ref)
        return _check_folder_existence(ref, "export", ref_layout.export())

    def recipe_metadata_path(self, ref: RecipeReference):
        """Returns the path of the recipe metadata files in the Conan cache

        Exceptionally, adding or modifying the files within this folder is allowed, as
        the metadata files are not taken into account into the computation of the recipe hash
        (recipe revision).

        :param ref: RecipeReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        ref = _resolve_latest_ref(cache, ref)
        ref_layout = cache.recipe_layout(ref)
        return _check_folder_existence(ref, "metadata", ref_layout.metadata())

    def export_source_path(self, ref: RecipeReference):
        """Returns the path of the exported sources in the Conan cache

        Note that the exported sources only exist in the cache when the package has been created
        locally or built from source.

        This folder is exclusively for **read-only** access, typically for debugging purposes,
        it is completely forbidden to modify any of its contents.

        :param ref: RecipeReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        ref = _resolve_latest_ref(cache, ref)
        ref_layout = cache.recipe_layout(ref)
        return _check_folder_existence(ref, "export_sources", ref_layout.export_sources())

    def source_path(self, ref: RecipeReference):
        """Returns the path of the temporary source folder in the Conan cache

        Note that the source folder only exist in the cache when the package has been created
        locally or built from source.

        This folder is exclusively for **read-only** access, typically for debugging purposes,
        it is completely forbidden to modify any of its contents.

        :param ref: RecipeReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        ref = _resolve_latest_ref(cache, ref)
        ref_layout = cache.recipe_layout(ref)
        return _check_folder_existence(ref, "source", ref_layout.source())

    def build_path(self, pref: PkgReference):
        """Returns the path of the temporary build folder in the Conan cache

        Note that the build folder only exist in the cache when the package has been created
        locally or built from source.

        This folder is exclusively for **read-only** access, typically for debugging purposes,
        it is completely forbidden to modify any of its contents.

        :param pref: PkgReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
           Exactly same behavior for the package revision.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        pref = _resolve_latest_pref(cache, pref)
        ref_layout = cache.pkg_layout(pref)
        return _check_folder_existence(pref, "build", ref_layout.build())

    def package_metadata_path(self, pref: PkgReference):
        """Returns the path of the package metadata folder in the Conan cache

        Exceptionally, adding or modifying the files within this folder is allowed, as
        the metadata files are not taken into account into the computation of the package hash
        (package revision).

       :param pref: PkgReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
           Exactly same behavior for the package revision.
       :return: path to the folder, as a string
       :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        pref = _resolve_latest_pref(cache, pref)
        ref_layout = cache.pkg_layout(pref)
        return _check_folder_existence(pref, "metadata", ref_layout.metadata())

    def package_path(self, pref: PkgReference):
        """Returns the path of the package folder in the Conan cache

        This folder is exclusively for **read-only** access, typically for debugging purposes,
        it is completely forbidden to modify any of its contents.

        :param pref: PkgReference. If it includes recipe revision, that exact revision will be
           returned, if it doesn't include recipe revision, it will return the latest revision one.
           Exactly same behavior for the package revision.
        :return: path to the folder, as a string
        :raises: ConanExcepcion if the folder doesn't exist
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        pref = _resolve_latest_pref(cache, pref)
        ref_layout = cache.pkg_layout(pref)
        if os.path.exists(ref_layout.finalize()):
            return ref_layout.finalize()
        return _check_folder_existence(pref, "package", ref_layout.package())

    def check_integrity(self, package_list, return_pkg_list=False):
        """
        Check if the recipes and packages are corrupted

        :param package_list: PackagesList to check
        :param return_pkg_list: If True, return a PackagesList with corrupted artifacts
        :return: PackagesList with corrupted artifacts if return_pkg_list is True
        :raises: ConanExcepcion if there are corrupted artifacts and return_pkg_list is False
        """
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        checker = IntegrityChecker(cache)
        corrupted_pkg_list = checker.check(package_list)
        if return_pkg_list:
            return corrupted_pkg_list
        if corrupted_pkg_list:
            raise ConanException("There are corrupted artifacts, check the error logs")

    def clean(self, package_list, source=True, build=True, download=True, temp=True,
              backup_sources=False) -> None:
        """
        Remove non critical folders from the cache, like source, build and download (.tgz store)
        folders.

        This method uses proper locking to prevent race conditions when multiple processes
        access the cache concurrently. Each operation acquires the appropriate lock before
        modifying filesystem or database state.

        :param package_list: the package lists that should be cleaned
        :param source: boolean, remove the "source" folder if True
        :param build: boolean, remove the "build" folder if True
        :param download: boolean, remove the "download (.tgz)" folder if True
        :param temp: boolean, remove the temporary folders
        :param backup_sources: boolean, remove the "source" folder if True
        :return:
        """

        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)

        # Temp folder cleaning: No lock needed
        # Rationale: UUID-based folder names make collisions extremely unlikely
        # These are orphaned/failed operations, safe to clean opportunistically
        if temp:
            rmdir(cache.temp_folder)
            # Clean those build folders that didn't succeed to create a package and wont be in DB
            builds_folder = cache.builds_folder
            if os.path.isdir(builds_folder):
                ConanOutput().verbose(f"Cleaning temporary folders")
                for subdir in os.listdir(builds_folder):
                    folder = os.path.join(builds_folder, subdir)
                    manifest = os.path.join(folder, "p", "conanmanifest.txt")
                    info = os.path.join(folder, "p", "conaninfo.txt")
                    if not os.path.exists(manifest) or not os.path.exists(info):
                        # These are failed builds, orphaned, safe to delete
                        rmdir(folder)

        # Temporary name (not named) until we have clarity if this is the same as the "t"
        # temporary (for exports) or not
        if os.path.exists(os.path.join(cache.store, "d")):
            rmdir(os.path.join(cache.store, "d"))

        # Backup sources cleaning: No lock needed
        # Rationale: These are in a separate download cache folder
        if backup_sources:
            backup_files = self._conan_api.cache.get_backup_sources(package_list, exclude=False,
                                                                    only_upload=False)
            ConanOutput().verbose(f"Cleaning {len(backup_files)} backup sources")
            for f in backup_files:
                remove(f)

        for ref, packages in package_list.items():
            ConanOutput(ref.repr_notime()).verbose("Cleaning recipe cache contents")
            ref_layout = cache.recipe_layout(ref)

            # Source folder: Use source_lock to prevent concurrent source operations
            # Lock level: SOURCE (30) - protects source() method and exports_sources retrieval
            if source:
                with cache._lock.source_lock(ref):
                    rmdir(ref_layout.source())

            # Download export folder: Use recipe_lock for recipe-level download folder
            # Lock level: RECIPE (20) - protects recipe-level resources
            if download:
                with cache._lock.recipe_lock(ref):
                    rmdir(ref_layout.download_export())

            # Package-level operations: Each package locked independently
            for pref in packages:
                ConanOutput(pref).verbose("Cleaning package cache contents")
                pref_layout = cache.pkg_layout(pref)

                # Package lock protects both filesystem AND database operations
                # Lock level: PACKAGE (40) - highest level lock
                # CRITICAL: build folder deletion and remove_build_id() must be atomic
                with cache._lock.package_lock(pref):
                    if build:
                        rmdir(pref_layout.build())
                        # It is important to remove the "build_id" identifier if build-folder is removed
                        # This DB write MUST be under the same lock as the folder deletion
                        cache.remove_build_id(pref)
                    if download:
                        rmdir(pref_layout.download_package())

    def save(self, package_list: PackagesList, path, no_source=False) -> None:
        """Create a compressed archive with recipes and packages from the Conan cache that
        can be later restored in another cache.

        Do not manipulate the contents of the resulting archive, as it also contains metadata,
        and modifying the contents would be equivalent to modify the Conan package cache, which
        is forbidden.

        :param package_list: PackagesList containing the recipes and packages to add
           to the compressed archive
        :param path: The archive file to generate. Based on the extension of the file, different
           compression formats can be used (.tgz, .txz and .tzst, the latter only for Python>=3.14).
        :param no_source: If True, the source folders in the cache will not be added to the archive.
        :return:
        """
        global_conf = self._api_helpers.global_conf
        cache = PkgCache(self._conan_api.cache_folder, global_conf)
        cache_folder = cache.store  # Note, this is not the home, but the actual package cache
        out = ConanOutput()
        mkdir(os.path.dirname(path))
        tgz_name = os.path.basename(path)
        compressformat = next((e for e in COMPRESSIONS if tgz_name.endswith(e)), None)
        if not compressformat:
            raise ConanException(f"Unsupported compression format for {tgz_name}")
        compresslevel = get_compress_level(compressformat, global_conf)
        tar_files: dict[str, str] = {}  # {path_in_tar: abs_path}

        for ref, packages in package_list.items():
            ref_layout = cache.recipe_layout(ref)
            recipe_folder = os.path.relpath(ref_layout.base_folder, cache_folder)
            recipe_folder = recipe_folder.replace("\\", "/")  # make win paths portable
            ref_bundle = package_list.recipe_dict(ref)
            ref_bundle["recipe_folder"] = recipe_folder
            out.info(f"Saving {ref}: {recipe_folder}")
            # Package only selected folders, not DOWNLOAD one
            for f in (EXPORT_FOLDER, EXPORT_SRC_FOLDER, SRC_FOLDER):
                if f == SRC_FOLDER and no_source:
                    continue
                cachepath = os.path.join(cache_folder, recipe_folder, f)
                if os.path.exists(cachepath):
                    tar_files[f"{recipe_folder}/{f}"] = cachepath
            cachepath = os.path.join(cache_folder, recipe_folder, DOWNLOAD_EXPORT_FOLDER, METADATA)
            if os.path.exists(cachepath):
                tar_files[f"{recipe_folder}/{DOWNLOAD_EXPORT_FOLDER}/{METADATA}"] = cachepath

            for pref in packages:
                pref_layout = cache.pkg_layout(pref)
                pkg_folder = pref_layout.package()
                folder = os.path.relpath(pkg_folder, cache_folder)
                folder = folder.replace("\\", "/")  # make win paths portable
                pkg_dict = package_list.package_dict(pref)
                pkg_dict["package_folder"] = folder
                out.info(f"Saving {pref}: {folder}")
                tar_files[folder] = os.path.join(cache_folder, folder)

                if os.path.exists(pref_layout.metadata()):
                    metadata_folder = os.path.relpath(pref_layout.metadata(), cache_folder)
                    metadata_folder = metadata_folder.replace("\\", "/")  # make paths portable
                    pkg_dict["metadata_folder"] = metadata_folder
                    out.info(f"Saving {pref} metadata: {metadata_folder}")
                    tar_files[metadata_folder] = os.path.join(cache_folder, metadata_folder)

        # Create a temporary file in order to reuse compress_files functionality
        # Use a unique temp file to avoid race conditions when running in parallel
        serialized = json.dumps(package_list.serialize(), indent=2)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', prefix='pkglist_',
                                         delete=False) as tmp_file:
            pkglist_path = tmp_file.name
            tmp_file.write(serialized)
        tar_files["pkglist.json"] = pkglist_path
        try:
            compress_files(tar_files, tgz_name, os.path.dirname(path), compresslevel, recursive=True)
        finally:
            remove(pkglist_path)
        ConanOutput().success(f"Created cache save file: {path}")

    def restore(self, path) -> PackagesList:
        """Restore a compressed archive with recipes and packages previously saved from another
        Conan cache into the currently active Conan cache.

        :param path: The archive file to restore. Based on the extension of the file, different
           compression formats can be used (.tgz, .txz and .tzst, the latter only for Python>=3.14).
        :return: a PackageLists with the recipes and packages that have been restored to the cache
        """
        if not os.path.isfile(path):
            raise ConanException(f"Restore archive doesn't exist in {path}")

        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        cache_folder = cache.store  # Note, this is not the home, but the actual package cache

        # Extract to a temporary directory first to avoid concurrent extraction conflicts
        # Multiple processes restoring the same package would otherwise overwrite each other's files
        with tempfile.TemporaryDirectory(prefix="conan_restore_") as temp_extract_dir:
            with open(path, mode='rb') as file_handler:
                the_tar = tarfile.open(fileobj=file_handler)
                fileobj = the_tar.extractfile("pkglist.json")
                pkglist = fileobj.read()
                the_tar.extraction_filter = (lambda member, _: member)  # fully_trusted (Py 3.14)
                # Extract to temp dir instead of directly to cache
                the_tar.extractall(path=temp_extract_dir)
                the_tar.close()

            # After unzipping the files, we need to update the DB that references these files
            out = ConanOutput()
            package_list = PackagesList.deserialize(json.loads(pkglist))
            self._restore_from_extracted(cache, cache_folder, temp_extract_dir,
                                        package_list, out)

        return package_list

    def _restore_from_extracted(self, cache, cache_folder, temp_extract_dir,
                               package_list, out):
        """Restore packages from extracted tarball in temp dir to cache with proper locking."""
        for ref, packages in package_list.items():
            ref_bundle = package_list.recipe_dict(ref)
            ref.timestamp = revision_timestamp_now()
            ref_bundle["timestamp"] = ref.timestamp

            # Create or get recipe layout
            # Handle concurrent creation - if another process creates it, just use that
            try:
                recipe_layout = cache.recipe_layout(ref)
            except ConanException:
                try:
                    recipe_layout = cache.create_ref_layout(ref)  # new DB folder entry
                except ConanException:
                    # Another process created it concurrently, get the existing one
                    recipe_layout = cache.recipe_layout(ref)

            recipe_folder = ref_bundle["recipe_folder"]

            # Copy recipe files from temp dir to cache under recipe lock
            # This prevents concurrent processes from racing on recipe file operations
            with cache._lock.recipe_lock(ref):
                temp_recipe_path = os.path.join(temp_extract_dir, recipe_folder)
                if os.path.exists(temp_recipe_path):
                    # Copy recipe folders (export, export_sources, etc.) if not already present
                    for item in os.listdir(temp_recipe_path):
                        src = os.path.join(temp_recipe_path, item)
                        dst = os.path.join(recipe_layout.base_folder, item)
                        if not os.path.exists(dst):
                            if os.path.isdir(src):
                                shutil.copytree(src, dst)
                            else:
                                mkdir(os.path.dirname(dst))
                                shutil.copy2(src, dst)

            out.info(f"Restore: {ref} in {recipe_folder}")
            for pref in packages:
                pref.timestamp = revision_timestamp_now()
                pref_bundle = package_list.package_dict(pref)
                pref_bundle["timestamp"] = pref.timestamp

                # First, create or get the package layout
                # This creates the DB entry if needed (with internal locking)
                # Handle concurrent creation gracefully
                try:
                    pkg_layout = cache.pkg_layout(pref)
                except ConanException:
                    try:
                        pkg_layout = cache.create_pkg_layout(pref)  # DB Folder entry
                        # If another process created it concurrently, create_pkg_layout returns None
                        if pkg_layout is None:
                            # Another process created it, get the existing layout
                            pkg_layout = cache.pkg_layout(pref)
                    except ConanException:
                        # Another process created it, get the existing layout
                        pkg_layout = cache.pkg_layout(pref)

                unzipped_pkg_folder = pref_bundle["package_folder"]
                out.info(f"Restore: {pref} in {unzipped_pkg_folder}")

                # Now acquire the package lock to do all folder operations atomically
                # This prevents concurrent restores from racing on folder copies
                with cache._lock.package_lock(pref):
                    # Copy package files from temp extraction dir to final location
                    temp_pkg_path = os.path.join(temp_extract_dir, unzipped_pkg_folder)

                    if os.path.exists(temp_pkg_path):
                        # Package is in temp dir, copy to final location if not already there
                        if not os.path.exists(pkg_layout.package()):
                            # First time this package is being restored
                            shutil.copytree(temp_pkg_path, pkg_layout.package())
                        # else: another concurrent process already restored it, skip

                    # Handle metadata folder
                    unzipped_metadata_folder = pref_bundle.get("metadata_folder")
                    if unzipped_metadata_folder:
                        out.info(f"Restore: {pref} metadata in {unzipped_metadata_folder}")
                        temp_meta_path = os.path.join(temp_extract_dir, unzipped_metadata_folder)

                        if os.path.exists(temp_meta_path):
                            if not os.path.exists(pkg_layout.metadata()):
                                # Copy metadata from temp dir
                                shutil.copytree(temp_meta_path, pkg_layout.metadata())
                            # else: another concurrent process already restored it, skip

        return package_list

    def get_backup_sources(self, package_list=None, exclude=True, only_upload=True):
        """Get list of backup source files currently present in the cache,
        either all of them if no argument, or filtered by those belonging to the references
        in the package_list

        :param package_list: a PackagesList object to filter backup files from (The files should
          have been downloaded form any of the references in the package_list)
        :param exclude: if True, exclude the sources that come from URLs present the
          core.sources:exclude_urls global conf
        :param only_upload: if True, only return the files for packages that are set to be uploaded
        :return: A list of files that need to be uploaded
        """
        config = self._api_helpers.global_conf
        download_cache_path = config.get("core.sources:download_cache")
        download_cache_path = download_cache_path or HomePaths(
            self._conan_api.cache_folder).default_sources_backup_folder
        excluded_urls = config.get("core.sources:exclude_urls",
                                   check_type=list, default=[]) if exclude else []
        download_cache = DownloadCache(download_cache_path)
        return download_cache.get_backup_sources_files(excluded_urls, package_list, only_upload)

    def path_to_ref(self, path):
        # This method is explicitly not publicly documented, as mostly a command helper for
        # debugging, it shouldn't be used in any real API usage
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        result = cache.path_to_ref(path)
        if result is None:
            base, folder = os.path.split(path)
            result = cache.path_to_ref(base)
        return result


def _resolve_latest_ref(cache, ref):
    if ref.revision is None or ref.revision == "latest":
        ref.revision = None
        result = cache.get_latest_recipe_revision(ref)
        if result is None:
            raise ConanException(f"'{ref}' not found in cache")
        ref = result
    return ref


def _resolve_latest_pref(cache, pref):
    pref.ref = _resolve_latest_ref(cache, pref.ref)
    if pref.revision is None or pref.revision == "latest":
        pref.revision = None
        result = cache.get_latest_package_revision(pref)
        if result is None:
            raise ConanException(f"'{pref.repr_notime()}' not found in cache")
        pref = result
    return pref


def _check_folder_existence(ref, folder_name, folder_path):
    if not os.path.exists(folder_path):
        raise ConanException(f"'{folder_name}' folder does not exist for the reference {ref}")
    return folder_path
