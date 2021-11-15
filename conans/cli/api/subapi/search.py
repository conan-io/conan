from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.search.search import search_recipes, filter_packages


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
    def filter_packages_configurations(self, pkg_configurations, query):
        """
        :param pkg_configurations: Dict[PkgReference, PackageConfiguration]
        :param query: str like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :return: Dict[PkgReference, PackageConfiguration]
        """
        return filter_packages(query, pkg_configurations)
