from conan.api.subapi import api_method
from conan.api.conan_app import ConanApp
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class CacheAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def exports_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export()

    @api_method
    def exports_sources_path(self, ref: RecipeReference):
        app = ConanApp(self.conan_api.cache_folder)
        ref = _resolve_latest_ref(app, ref)
        ref_layout = app.cache.ref_layout(ref)
        return ref_layout.export_sources()

    @api_method
    def sources_path(self, ref: RecipeReference):
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
    if ref.revision == "latest":
        ref.revision = None
        ref = app.cache.get_latest_recipe_reference(ref)
    return ref


def _resolve_latest_pref(app, pref):
    if pref.ref.revision == "latest":
        pref.ref.revision = None
        tmp = app.cache.get_latest_recipe_reference(pref.ref)
        pref.ref.revision = tmp.revision
    if pref.revision == "latest":
        pref.revision = None
        tmp = app.cache.get_latest_package_reference(pref)
        pref.revision = tmp.revision
    return pref
