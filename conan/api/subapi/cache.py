import json
import os
import tarfile
import tempfile
from contextlib import nullcontext

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
from conan.internal.api.uploader import PackagePreparator
from conan.internal.rest.pkg_sign import PkgSignaturesPlugin
from conan.internal.util.dates import revision_timestamp_now
from conan.internal.util.files import (mkdir, remove, remove_if_dirty, rmdir, save,
                                       set_dirty_context_manager)


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

    def sign(self, package_list):
        """Sign packages with the package signing plugin"""
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        pkg_signer = PkgSignaturesPlugin(cache, self._conan_api.home_folder)
        if not pkg_signer.is_sign_configured:
            raise ConanException(
                "The sign() function in the package sign plugin is not defined. For more "
                "information on how to configure the plugin, please read the documentation at "
                "https://docs.conan.io/2/reference/extensions/package_signing.html.")

        loader = self._api_helpers.loader
        preparator = PackagePreparator(loader, self._api_helpers.cache,
                                       self._api_helpers.remote_manager,
                                       self._api_helpers.global_conf)
        # Some packages can have missing sources/exports_sources
        enabled_remotes = self._conan_api.remotes.list()
        preparator.prepare(package_list, enabled_remotes, None, force=True)

        for rref, packages in package_list.items():
            recipe_bundle = package_list.recipe_dict(rref)
            rref_folder = cache.recipe_layout(rref).download_export()
            try:
                pkg_signer.sign_pkg(rref, recipe_bundle.get("files", {}), rref_folder)
            except Exception as e:
                recipe_bundle["pkgsign_error"] = str(e)
            for pref in packages:
                pkg_bundle = package_list.package_dict(pref)
                if pkg_bundle:
                    pref_folder = cache.pkg_layout(pref).download_package()
                    try:
                        pkg_signer.sign_pkg(pref, pkg_bundle.get("files", {}), pref_folder)
                    except Exception as e:
                        pkg_bundle["pkgsign_error"] = str(e)
        return package_list

    def verify(self, package_list):
        """Verify packages with the package signing plugin"""
        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        pkg_signer = PkgSignaturesPlugin(cache, self._conan_api.home_folder)
        if not pkg_signer.is_verify_configured:
            raise ConanException(
                "The verify() function in the package sign plugin is not defined. For more "
                "information on how to configure the plugin, please read the documentation at "
                "https://docs.conan.io/2/reference/extensions/package_signing.html.")

        for rref, packages in package_list.items():
            recipe_bundle = package_list.recipe_dict(rref)
            layout = cache.recipe_layout(rref)
            rref_folder = layout.download_export()
            files = {file: os.path.join(rref_folder, file) for file in
                     sorted(os.listdir(rref_folder)) if not file.startswith(METADATA)}
            recipe_bundle["files"] = files
            try:
                pkg_signer.verify(rref, rref_folder, layout.metadata(), files)
            except Exception as e:
                recipe_bundle["pkgsign_error"] = str(e)
            for pref in packages:
                pkg_bundle = package_list.package_dict(pref)
                if pkg_bundle:
                    layout = cache.pkg_layout(pref)
                    pref_folder = layout.download_package()
                    files = {file: os.path.join(pref_folder, file) for file in
                             sorted(os.listdir(pref_folder)) if not file.startswith(METADATA)}
                    pkg_bundle["files"] = files
                    try:
                        pkg_signer.verify(pref, pref_folder, layout.metadata(), files)
                    except Exception as e:
                        pkg_bundle["pkgsign_error"] = str(e)
        return package_list

    def clean(self, package_list, source=True, build=True, download=True, temp=True,
              backup_sources=False) -> None:
        """
        Remove non critical folders from the cache, like source, build and download (.tgz store)
        folders.

        :param package_list: the package lists that should be cleaned
        :param source: boolean, remove the "source" folder if True
        :param build: boolean, remove the "build" folder if True
        :param download: boolean, remove the "download (.tgz)" folder if True
        :param temp: boolean, remove the temporary folders
        :param backup_sources: boolean, remove the "source" folder if True
        :return:
        """

        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
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
                        rmdir(folder)

        if backup_sources:
            backup_files = self._conan_api.cache.get_backup_sources(package_list, exclude=False,
                                                                    only_upload=False)
            ConanOutput().verbose(f"Cleaning {len(backup_files)} backup sources")
            for f in backup_files:
                remove(f)

        for ref, packages in package_list.items():
            ConanOutput(ref.repr_notime()).verbose("Cleaning recipe cache contents")
            ref_layout = cache.recipe_layout(ref)
            if source:
                rmdir(ref_layout.source())
            if download:
                rmdir(ref_layout.download_export())
            for pref in packages:
                ConanOutput(pref).verbose("Cleaning package cache contents")
                pref_layout = cache.pkg_layout(pref)
                if build:
                    rmdir(pref_layout.build())
                    # It is important to remove the "build_id" identifier if build-folder is removed
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
        serialized = json.dumps(package_list.serialize(), indent=2)
        pkglist_path = os.path.join(tempfile.gettempdir(), "pkglist.json")
        save(pkglist_path, serialized)
        tar_files["pkglist.json"] = pkglist_path
        compress_files(tar_files, tgz_name, os.path.dirname(path), compresslevel, recursive=True)
        remove(pkglist_path)
        ConanOutput().success(f"Created cache save file: {path}")

    def restore(self, path) -> PackagesList:
        """Restore a compressed archive with recipes and packages previously saved from another
        Conan cache into the currently active Conan cache.

        The folders of the origin cache are not necessarily the folders of this cache, so the
        destination is resolved in the cache DB before extracting, and every folder is extracted
        directly to its final location. Recipes and packages are immutable, so the revisions
        already in this cache are not extracted again, only the missing ones.

        :param path: The archive file to restore. Based on the extension of the file, different
           compression formats can be used (.tgz, .txz and .tzst, the latter only for Python>=3.14).
        :return: a PackageLists with the recipes and packages that have been restored to the cache
        """
        if not os.path.isfile(path):
            raise ConanException(f"Restore archive doesn't exist in {path}")

        cache = PkgCache(self._conan_api.cache_folder, self._api_helpers.global_conf)
        cache_folder = cache.store  # Note, this is not the home, but the actual package cache
        out = ConanOutput()
        plan = _RestorePlan(cache_folder)
        new_recipes, new_packages = [], []  # New DB entries, removed if they are not restored

        with open(path, mode='rb') as file_handler:
            the_tar = tarfile.open(fileobj=file_handler)
            the_tar.extraction_filter = (lambda member, _: member)  # fully_trusted (Py 3.14)
            pkglist = the_tar.extractfile("pkglist.json").read()
            package_list = PackagesList.deserialize(json.loads(pkglist))

            # First the DB, to know the final cache folder for every folder in the archive
            for ref, packages in package_list.items():
                ref_bundle = package_list.recipe_dict(ref)
                ref.timestamp = revision_timestamp_now()
                ref_bundle["timestamp"] = ref.timestamp
                recipe_folder = ref_bundle["recipe_folder"]  # The folder in the archive
                export_folder = f"{recipe_folder}/{EXPORT_FOLDER}"
                try:
                    recipe_layout = cache.recipe_layout(ref)
                    replace = False
                except ConanException:
                    recipe_layout = cache.create_ref_layout(ref)  # new DB folder entry
                    replace = True  # not in the DB, whatever is in the folder is a leftover
                    new_recipes.append((recipe_layout, export_folder))
                dest_folder = _cache_path(recipe_layout.base_folder, cache_folder)
                ref_bundle["recipe_folder"] = dest_folder
                out.info(f"Restore: {ref} in {dest_folder}")
                plan.add_contents(export_folder, recipe_layout.export(), replace)
                plan.add_contents(f"{recipe_folder}/{EXPORT_SRC_FOLDER}",
                                  recipe_layout.export_sources(), replace)
                # The sources get the same dirty protection they have when they are obtained
                # by "conan source", incomplete ones are discarded, not used as valid sources
                remove_if_dirty(recipe_layout.source())
                plan.add_contents(f"{recipe_folder}/{SRC_FOLDER}", recipe_layout.source(),
                                  replace, dirty=True)
                plan.add_metadata(f"{recipe_folder}/{DOWNLOAD_EXPORT_FOLDER}/{METADATA}",
                                  recipe_layout.metadata())

                for pref in packages:
                    pref.timestamp = revision_timestamp_now()
                    pref_bundle = package_list.package_dict(pref)
                    pref_bundle["timestamp"] = pref.timestamp
                    pkg_folder = pref_bundle["package_folder"]  # The folder in the archive
                    try:
                        pkg_layout = cache.pkg_layout(pref)
                        # A dirty package is incomplete, the leftover of an interrupted restore
                        # or download, it is removed to restore it again
                        remove_if_dirty(pkg_layout.package())
                        replace = False
                    except ConanException:
                        pkg_layout = cache.create_pkg_layout(pref)  # new DB folder entry
                        replace = True
                        new_packages.append((pkg_layout, pkg_folder))
                    dest_folder = _cache_path(pkg_layout.package(), cache_folder)
                    pref_bundle["package_folder"] = dest_folder
                    out.info(f"Restore: {pref} in {dest_folder}")
                    plan.add_contents(pkg_folder, pkg_layout.package(), replace, dirty=True)
                    metadata_folder = pref_bundle.get("metadata_folder")
                    if metadata_folder:
                        dest_folder = _cache_path(pkg_layout.metadata(), cache_folder)
                        pref_bundle["metadata_folder"] = dest_folder
                        out.info(f"Restore: {pref} metadata in {dest_folder}")
                        plan.add_metadata(metadata_folder, pkg_layout.metadata())

            try:
                plan.extract(the_tar)
            except BaseException:
                # A new DB entry without contents would be a broken recipe or package in the
                # cache, remove the ones that couldn't be restored, leaving the rest usable
                _remove_not_restored(cache, plan, new_recipes, new_packages)
                raise
            the_tar.close()

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


def _cache_path(folder, cache_folder):
    return os.path.relpath(folder, cache_folder).replace("\\", "/")  # make win paths portable


class _RestorePlan:
    """ Where every folder of a "conan cache save" archive has to be extracted in this cache,
    which is not necessarily the folder it had in the cache that created the archive

    The plan is built first, adding every folder of the archive that has to be restored, and
    then it is executed with "extract()". Only the folders added to the plan are extracted, and
    they are extracted directly to the destination the cache DB assigned to them in this cache,
    so no other contents of the archive are written to the cache store.
    """

    def __init__(self, cache_folder):
        """
        :param cache_folder: The cache store folder, the root all the extractions are relative to
        """
        self._cache_folder = cache_folder
        self._folders = {}  # {folder in the archive: folder in the cache, relative to the store}
        self._dirty = set()  # Folders marked while they are extracted, to detect incomplete ones
        self._restored = set()  # Folders already extracted

    def add_contents(self, folder, dest, replace, dirty=False):
        """ Add a folder of recipe or package contents to the plan, unless it is already in this
        cache. Recipes and packages are immutable, if the revision is already in this cache the
        contents are the same, and they are not extracted again, so their files are never
        overwritten. The contents of a revision that is not in the DB are leftovers, not valid
        contents, and they are replaced

        :param folder: The folder in the archive, as it was in the cache that created it
        :param dest: The absolute folder in this cache where those contents have to be extracted
        :param replace: If True, existing contents in ``dest`` are leftovers and are removed
           before extracting. If False, ``dest`` contents are valid and nothing is extracted
        :param dirty: If True, ``dest`` is marked as dirty while it is extracted, so an
           interrupted extraction leaves incomplete contents that will not be used
        """
        if os.path.exists(dest):
            if not replace:
                return
            rmdir(dest)
        self._folders[folder] = _cache_path(dest, self._cache_folder)
        if dirty:
            self._dirty.add(folder)

    def add_metadata(self, folder, dest):
        """ Add a metadata folder to the plan. Metadata is not immutable, it is always restored,
        adding to the existing one

        :param folder: The metadata folder in the archive
        :param dest: The absolute metadata folder in this cache where it has to be extracted
        """
        self._folders[folder] = _cache_path(dest, self._cache_folder)

    def restored(self, folder):
        """ If the contents of an archive folder were already extracted, used after a failure to
        know which new DB entries have contents and which ones have to be removed

        :param folder: The folder in the archive
        :return: True if that folder was already extracted
        """
        return folder in self._restored

    def extract(self, the_tar):
        """ Extract the planned folders, one folder at a time, in the order they are in the
        archive, so the stream is read forwards, and an interrupted extraction only leaves one
        incomplete folder. Members that do not belong to any planned folder are not extracted

        :param the_tar: The open tarfile of the "conan cache save" archive to restore
        """
        groups = {}  # {folder in the archive: [members]}, in the order of the archive
        for member in the_tar.getmembers():
            located = self._locate(member.name)
            if located is not None:  # Not restored, like "pkglist.json" or existing contents
                folder, member.name = located
                groups.setdefault(folder, []).append(member)

        for folder, members in groups.items():
            dest = os.path.join(self._cache_folder, self._folders[folder])
            # The mark stays if the extraction is interrupted, so the contents are not used
            mark = set_dirty_context_manager(dest) if folder in self._dirty else nullcontext()
            with mark:
                the_tar.extractall(path=self._cache_folder, members=members)
            self._restored.add(folder)

    def _locate(self, name):
        """ The folder to restore this archive member belongs to, and the path, relative to the
        cache store, where it has to be extracted

        The member is a path in the archive, and only its folders are known, so the member path
        is checked from the longest to the shortest prefix, until one of them is a folder to
        restore, and the rest of the member path is appended to that folder destination:
           "abcde1234/e/conanfile.py" with {"abcde1234/e": "fghij5678/e"} is extracted as
           "fghij5678/e/conanfile.py"

        :param name: The member path in the archive
        :return: A tuple (folder in the archive, path relative to the cache store where the
           member has to be extracted), or None if the member does not belong to any planned
           folder, so it is not restored, like "pkglist.json" or the contents already in this
           cache, but also any member trying to escape the folders of the plan
        """
        parts = name.split("/")
        for i in range(len(parts), 0, -1):
            folder = "/".join(parts[:i])
            dest = self._folders.get(folder)
            if dest is not None:
                return folder, "/".join([dest] + parts[i:])
        return None


def _remove_not_restored(cache, plan, recipes, packages):
    """ Remove the new DB entries whose contents were not restored, so a failed restore doesn't
    leave the cache with references to recipes or packages that are not there
    """
    removed_refs = set()
    for recipe_layout, folder in recipes:
        if not plan.restored(folder):
            # It also removes its packages, all of them new, this recipe revision was not here
            cache.remove_recipe_layout(recipe_layout)
            removed_refs.add(repr(recipe_layout.reference))
    for pkg_layout, folder in packages:
        if not plan.restored(folder) and repr(pkg_layout.reference.ref) not in removed_refs:
            cache.remove_package_layout(pkg_layout)


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
