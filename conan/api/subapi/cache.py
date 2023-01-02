from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp
from conans.errors import ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class CacheAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def export_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export()

    @api_method
    def export_source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export_sources()

    @api_method
    def source_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.source()

    @api_method
    def build_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.build()

    @api_method
    def package_path(self, pref: PkgReference):
        app = ConanApp(self.conan_api.cache_folder)
        pref = _resolve_latest_pref(app, pref)
        ref_layout = app.cache.pkg_layout(pref)
        return ref_layout.package()


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
