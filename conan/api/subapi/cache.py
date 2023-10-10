import json
import os
import tarfile

from conan.api.model import MultiPackagesList
from conan.api.output import ConanOutput
from conan.internal.conan_app import ConanApp
from conan.internal.integrity_check import IntegrityChecker
from conans.client.cache.cache import ClientCache
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.dates import revision_timestamp_now
from conans.util.files import rmdir, gzopen_without_timestamps, save, load


class CacheAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def export_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return ref_layout.export()

    def recipe_metadata_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.recipe_layout(ref)
        return ref_layout.metadata()

    def export_source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return ref_layout.export_sources()

    def source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref.revision = None if ref.revision == "latest" else ref.revision
        ref_layout = app.cache.recipe_layout(ref)
        return ref_layout.source()

    def build_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.build()

    def package_metadata_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.metadata()

    def package_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.package()

    def check_integrity(self, package_list):
        """Check if the recipes and packages are corrupted (it will raise a ConanExcepcion)"""
        app = ConanApp(self.conan_api.cache_folder)
        checker = IntegrityChecker(app)
        checker.check(package_list)

    def clean(self, package_list, source=True, build=True, download=True, temp=True):
        """
        Remove non critical folders from the cache, like source, build and download (.tgz store)
        folders.
        :param package_list: the package lists that should be cleaned
        :param source: boolean, remove the "source" folder if True
        :param build: boolean, remove the "build" folder if True
        :param download: boolen, remove the "download (.tgz)" folder if True
        :param temp: boolean, remove the temporary folders
        :return:
        """

        app = ConanApp(self.conan_api.cache_folder)
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

    def get(self, package_list):
        multi_package_list = MultiPackagesList.load(package_list)
        package_list = multi_package_list["Local Cache"]
        app = ConanApp(self.conan_api.cache_folder)
        ref_folders = {}
        for ref, ref_bundle in package_list.refs().items():
            ref_layout = app.cache.recipe_layout(ref)
            base_folder = ref_layout.base_folder
            ref_folders[ref] = base_folder
            for pref, _ in package_list.prefs(ref, ref_bundle).items():
                pref_layout = app.cache.pkg_layout(pref)
                base_folder = pref_layout.package()
                # FIXME: Missing metadata
                ref_folders[pref] = base_folder

        tgz_path = os.path.abspath("cache.tgz")
        _compress_cache(tgz_path, ref_folders, self.conan_api.cache_folder)

    def put(self, path):
        with open(path, mode='rb') as file_handler:
            the_tar = tarfile.open(fileobj=file_handler)
            # NOTE: The errorlevel=2 has been removed because it was failing in Win10, it didn't allow to
            # "could not change modification time", with time=0
            # the_tar.errorlevel = 2  # raise exception if any error
            the_tar.list(verbose=True)
            the_tar.extractall(path=self.conan_api.cache_folder)
            the_tar.close()

        manifest_path = os.path.join(self.conan_api.cache_folder, "cache_manifest.json")
        manifest = load(manifest_path)
        os.remove(manifest_path)  # remove file from the cache
        manifest = json.loads(manifest)
        print(manifest)
        cache = ClientCache(self.conan_api.cache_folder)
        for ref, folder in manifest.items():
            print(repr(ref), folder)
            if ":" in ref:  # Package
                pref = PkgReference.loads(ref)
            else:
                ref = RecipeReference.loads(ref)
                ref.timestamp = revision_timestamp_now()
                recipe_layout = cache.get_or_create_ref_layout(ref)
                rel_path = os.path.relpath(recipe_layout.base_folder, cache.cache_folder)
                assert rel_path == folder, f"{rel_path}!={folder}"



def _compress_cache(tgz_path, ref_folders, cache_folder):
    name = os.path.basename(tgz_path)
    out = ConanOutput()
    serialized = {ref.repr_notime(): os.path.relpath(f, cache_folder)
                  for ref, f in ref_folders.items()}
    serialized = json.dumps(serialized, indent=2)
    manifest_path = os.path.join(cache_folder, "cache_manifest.json")
    save(manifest_path, serialized)
    with open(tgz_path, "wb") as tgz_handle:
        tgz = gzopen_without_timestamps(name, mode="w", fileobj=tgz_handle)
        tgz.add(manifest_path, "cache_manifest.json")
        for ref, folder in ref_folders.items():
            rel_path = os.path.relpath(folder, cache_folder)
            out.info(f"Compressing {ref}: {rel_path}")
            tgz.add(folder, rel_path, recursive=True)
        tgz.close()


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
