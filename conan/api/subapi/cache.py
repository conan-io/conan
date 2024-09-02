import json
import os
import shutil
import tarfile
from io import BytesIO

from conan.api.model import PackagesList
from conan.api.output import ConanOutput
from conan.internal.cache.cache import PkgCache
from conan.internal.cache.home_paths import HomePaths
from conan.internal.conan_app import ConanApp
from conan.internal.cache.integrity_check import IntegrityChecker
from conans.client.downloaders.download_cache import DownloadCache
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.dates import revision_timestamp_now
from conans.util.files import rmdir, gzopen_without_timestamps, mkdir, remove


class CacheAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def export_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return _check_folder_existence(ref, "export", ref_layout.export())

    def recipe_metadata_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.recipe_layout(ref)
        return _check_folder_existence(ref, "metadata", ref_layout.metadata())

    def export_source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return _check_folder_existence(ref, "export_sources", ref_layout.export_sources())

    def source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return _check_folder_existence(ref, "source", ref_layout.source())

    def build_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return _check_folder_existence(pref, "build", ref_layout.build())

    def package_metadata_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return _check_folder_existence(pref, "metadata", ref_layout.metadata())

    def package_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        if os.path.exists(ref_layout.finalize()):
            return ref_layout.finalize()
        return _check_folder_existence(pref, "package", ref_layout.package())

    def check_integrity(self, package_list):
        """Check if the recipes and packages are corrupted (it will raise a ConanExcepcion)"""
        app = ConanApp(self.conan_api)
        checker = IntegrityChecker(app)
        checker.check(package_list)

    def clean(self, package_list, source=True, build=True, download=True, temp=True,
              backup_sources=False):
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

        app = ConanApp(self.conan_api)
        if temp:
            rmdir(app.cache.temp_folder)
            # Clean those build folders that didn't succeed to create a package and wont be in DB
            builds_folder = app.cache.builds_folder
            if os.path.isdir(builds_folder):
                for subdir in os.listdir(builds_folder):
                    folder = os.path.join(builds_folder, subdir)
                    manifest = os.path.join(folder, "p", "conanmanifest.txt")
                    info = os.path.join(folder, "p", "conaninfo.txt")
                    if not os.path.exists(manifest) or not os.path.exists(info):
                        rmdir(folder)
        if backup_sources:
            backup_files = self.conan_api.cache.get_backup_sources(package_list, exclude=False, only_upload=False)
            for f in backup_files:
                remove(f)

        for ref, ref_bundle in package_list.refs().items():
            ref_layout = app.cache.recipe_layout(ref)
            if source:
                rmdir(ref_layout.source())
            if download:
                rmdir(ref_layout.download_export())
            for pref, _ in package_list.prefs(ref, ref_bundle).items():
                pref_layout = app.cache.pkg_layout(pref)
                if build:
                    rmdir(pref_layout.build())
                    # It is important to remove the "build_id" identifier if build-folder is removed
                    app.cache.remove_build_id(pref)
                if download:
                    rmdir(pref_layout.download_package())

    def save(self, package_list, tgz_path):
        global_conf = self.conan_api.config.global_conf
        cache = PkgCache(self.conan_api.cache_folder, global_conf)
        cache_folder = cache.store  # Note, this is not the home, but the actual package cache
        out = ConanOutput()
        mkdir(os.path.dirname(tgz_path))
        name = os.path.basename(tgz_path)
        compresslevel = global_conf.get("core.gzip:compresslevel", check_type=int)
        with open(tgz_path, "wb") as tgz_handle:
            tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle,
                                            compresslevel=compresslevel)
            for ref, ref_bundle in package_list.refs().items():
                ref_layout = cache.recipe_layout(ref)
                recipe_folder = os.path.relpath(ref_layout.base_folder, cache_folder)
                recipe_folder = recipe_folder.replace("\\", "/")  # make win paths portable
                ref_bundle["recipe_folder"] = recipe_folder
                out.info(f"Saving {ref}: {recipe_folder}")
                tgz.add(os.path.join(cache_folder, recipe_folder), recipe_folder, recursive=True)
                for pref, pref_bundle in package_list.prefs(ref, ref_bundle).items():
                    pref_layout = cache.pkg_layout(pref)
                    pkg_folder = pref_layout.package()
                    folder = os.path.relpath(pkg_folder, cache_folder)
                    folder = folder.replace("\\", "/")  # make win paths portable
                    pref_bundle["package_folder"] = folder
                    out.info(f"Saving {pref}: {folder}")
                    tgz.add(os.path.join(cache_folder, folder), folder, recursive=True)
                    if os.path.exists(pref_layout.metadata()):
                        metadata_folder = os.path.relpath(pref_layout.metadata(), cache_folder)
                        metadata_folder = metadata_folder.replace("\\", "/")  # make paths portable
                        pref_bundle["metadata_folder"] = metadata_folder
                        out.info(f"Saving {pref} metadata: {metadata_folder}")
                        tgz.add(os.path.join(cache_folder, metadata_folder), metadata_folder,
                                recursive=True)
            serialized = json.dumps(package_list.serialize(), indent=2)
            info = tarfile.TarInfo(name="pkglist.json")
            data = serialized.encode('utf-8')
            info.size = len(data)
            tgz.addfile(tarinfo=info, fileobj=BytesIO(data))
            tgz.close()

    def restore(self, path):
        if not os.path.isfile(path):
            raise ConanException(f"Restore archive doesn't exist in {path}")

        cache = PkgCache(self.conan_api.cache_folder, self.conan_api.config.global_conf)
        cache_folder = cache.store  # Note, this is not the home, but the actual package cache

        with open(path, mode='rb') as file_handler:
            the_tar = tarfile.open(fileobj=file_handler)
            fileobj = the_tar.extractfile("pkglist.json")
            pkglist = fileobj.read()
            the_tar.extractall(path=cache_folder)
            the_tar.close()

        # After unzipping the files, we need to update the DB that references these files
        out = ConanOutput()
        package_list = PackagesList.deserialize(json.loads(pkglist))
        for ref, ref_bundle in package_list.refs().items():
            ref.timestamp = revision_timestamp_now()
            ref_bundle["timestamp"] = ref.timestamp
            try:
                recipe_layout = cache.recipe_layout(ref)
            except ConanException:
                recipe_layout = cache.create_ref_layout(ref)  # new DB folder entry
            recipe_folder = ref_bundle["recipe_folder"]
            rel_path = os.path.relpath(recipe_layout.base_folder, cache_folder)
            rel_path = rel_path.replace("\\", "/")
            # In the case of recipes, they are always "in place", so just checking it
            assert rel_path == recipe_folder, f"{rel_path}!={recipe_folder}"
            out.info(f"Restore: {ref} in {recipe_folder}")
            for pref, pref_bundle in package_list.prefs(ref, ref_bundle).items():
                pref.timestamp = revision_timestamp_now()
                pref_bundle["timestamp"] = pref.timestamp
                try:
                    pkg_layout = cache.pkg_layout(pref)
                except ConanException:
                    pkg_layout = cache.create_pkg_layout(pref)  # DB Folder entry
                # FIXME: This is not taking into account the existence of previous package
                unzipped_pkg_folder = pref_bundle["package_folder"]
                out.info(f"Restore: {pref} in {unzipped_pkg_folder}")
                # If the DB folder entry is different to the disk unzipped one, we need to move it
                # This happens for built (not downloaded) packages in the source "conan cache save"
                db_pkg_folder = os.path.relpath(pkg_layout.package(), cache_folder)
                db_pkg_folder = db_pkg_folder.replace("\\", "/")
                if db_pkg_folder != unzipped_pkg_folder:
                    # If a previous package exists, like a previous restore, then remove it
                    if os.path.exists(pkg_layout.package()):
                        shutil.rmtree(pkg_layout.package())
                    shutil.move(os.path.join(cache_folder, unzipped_pkg_folder),
                                pkg_layout.package())
                    pref_bundle["package_folder"] = db_pkg_folder
                unzipped_metadata_folder = pref_bundle.get("metadata_folder")
                if unzipped_metadata_folder:
                    # FIXME: Restore metadata is not incremental, but destructive
                    out.info(f"Restore: {pref} metadata in {unzipped_metadata_folder}")
                    db_metadata_folder = os.path.relpath(pkg_layout.metadata(), cache_folder)
                    db_metadata_folder = db_metadata_folder.replace("\\", "/")
                    if db_metadata_folder != unzipped_metadata_folder:
                        # We need to put the package in the final location in the cache
                        if os.path.exists(pkg_layout.metadata()):
                            shutil.rmtree(pkg_layout.metadata())
                        shutil.move(os.path.join(cache_folder, unzipped_metadata_folder),
                                    pkg_layout.metadata())
                        pref_bundle["metadata_folder"] = db_metadata_folder

        return package_list

    def get_backup_sources(self, package_list=None, exclude=True, only_upload=True):
        """Get list of backup source files currently present in the cache,
        either all of them if no argument, or filtered by those belonging to the references in the package_list

        @param package_list: a PackagesList object to filter backup files from (The files should have been downloaded form any of the references in the package_list)
        @param exclude: if True, exclude the sources that come from URLs present the core.sources:exclude_urls global conf
        @param only_upload: if True, only return the files for packages that are set to be uploaded
        """
        config = self.conan_api.config.global_conf
        download_cache_path = config.get("core.sources:download_cache")
        download_cache_path = download_cache_path or HomePaths(
            self.conan_api.cache_folder).default_sources_backup_folder
        excluded_urls = config.get("core.sources:exclude_urls", check_type=list, default=[]) if exclude else []
        download_cache = DownloadCache(download_cache_path)
        return download_cache.get_backup_sources_files(excluded_urls, package_list, only_upload)


def _resolve_latest_ref(app, ref):
    if ref.revision is None or ref.revision == "latest":
        ref.revision = None
        result = app.cache.get_latest_recipe_reference(ref)
        if result is None:
            raise ConanException(f"'{ref}' not found in cache")
        ref = result
    return ref


def _resolve_latest_pref(app, pref):
    pref.ref = _resolve_latest_ref(app, pref.ref)
    if pref.revision is None or pref.revision == "latest":
        pref.revision = None
        result = app.cache.get_latest_package_reference(pref)
        if result is None:
            raise ConanException(f"'{pref.repr_notime()}' not found in cache")
        pref = result
    return pref


def _check_folder_existence(ref, folder_name, folder_path):
    if not os.path.exists(folder_path):
        raise ConanException(f"'{folder_name}' folder does not exist for the reference {ref}")
    return folder_path
