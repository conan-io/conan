from typing import Dict

from conans.cli.api.model import PackageSearchInfo, Remote
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.search import search_recipes, filter_packages, search_packages


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipes(self, query: str, remote=None):
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            references = app.remote_manager.search_recipes(remote, query)
        else:
            references = search_recipes(app.cache, query)
        return references

    @api_method
    def packages(self, ref: RecipeReference, query: str, remote=None):
        assert ref.revision is not None, "packages: ref should have a revision. " \
                                         "Check latest if needed."
        if not remote:
            app = ConanApp(self.conan_api.cache_folder)
            package_ids = app.cache.get_package_references(ref)
            package_layouts = []
            for pkg in package_ids:
                latest_prev = app.cache.get_latest_package_reference(pkg)
                package_layouts.append(app.cache.pkg_layout(latest_prev))
            packages = search_packages(package_layouts, None)
            results = {pref: PackageSearchInfo(data) for pref, data in packages.items()}
            return _filter_packages(results, query)
        else:
            app = ConanApp(self.conan_api.cache_folder)
            packages = app.remote_manager.search_packages(remote, ref)
            results = {pref: PackageSearchInfo(data) for pref, data in packages.items()}
            return _filter_packages(results, query)


def _filter_packages(results:  Dict[PkgReference, PackageSearchInfo],
                     query: str) -> Dict[PkgReference, PackageSearchInfo]:
    filtered = filter_packages(query, results)
    return filtered

