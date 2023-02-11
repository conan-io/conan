from conan.internal.conan_app import ConanApp
from conan.internal.integrity_check import IntegrityChecker
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.files import rmdir


class CacheAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def export_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export()

    def export_source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export_sources()

    def source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.source()

    def build_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.build()

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

    def clean(self, package_list, source=None, build=None, download=None):
        """
        Remove non critical folders from the cache, like source, build and download (.tgz store)
        folders.
        :param package_list: the package lists that should be cleaned
        :param source: boolean, remove the "source" folder if True
        :param build: boolean, remove the "build" folder if True
        :param download: boolena, remove the "download (.tgz)" folder if True
        :return:
        """
        app = ConanApp(self.conan_api.cache_folder)
        for ref, ref_bundle in package_list.refs():
            ref_layout = app.cache.ref_layout(ref)
            if source:
                rmdir(ref_layout.source())
            if download:
                rmdir(ref_layout.download_export())
            for pref, _ in package_list.prefs(ref, ref_bundle):
                pref_layout = app.cache.pkg_layout(pref)
                if build:
                    rmdir(pref_layout.build())
                if download:
                    rmdir(pref_layout.download_package())


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
