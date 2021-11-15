from conans.cli.api.model import PackageSearchInfo
from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.model.recipe_ref import RecipeReference
from conans.search.search import search_recipes, filter_packages, get_packages_search_info


class SearchAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipes(self, query: str, remote=None):
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            return app.remote_manager.search_recipes(remote, query)
        else:
            references = search_recipes(app.cache, query)
            # For consistency with the remote search, we return references without revisions
            # user could use further the API to look for the revisions
            ret = []
            for r in references:
                r.revision = None
                r.timestamp = None
                if r not in ret:
                    ret.append(r)
            return ret

    @api_method
    def packages(self, ref: RecipeReference, query: str, remote=None):
        assert ref.revision is not None, "packages: ref should have a revision. " \
                                         "Check latest if needed."
        if not remote:
            app = ConanApp(self.conan_api.cache_folder)
            prefs = app.cache.get_package_references(ref)
            packages = get_packages_search_info(app.cache, prefs)
            results = {pref: PackageSearchInfo(data) for pref, data in packages.items()}
            return filter_packages(query, results)
        else:
            app = ConanApp(self.conan_api.cache_folder)
            packages = app.remote_manager.search_packages(remote, ref)
            results = {pref: PackageSearchInfo(data) for pref, data in packages.items()}
            return filter_packages(query, results)
