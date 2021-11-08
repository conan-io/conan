from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.search.search import search_packages


class ListAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def _get_revisions(self, ref, getter_name, remote=None):
        """
        Get all the recipe/package revisions given a reference from cache or remote.

        :param ref: `PkgReference` or `RecipeReference` without the revisions
        :param getter_name: `string` method that should be called by either app.remote_manager
                            or app.cache (remote or local search) to get all the revisions, e.g.:
                                >> app.remote_manager.get_package_revisions_references(ref, remote=remote)
                                >> app.cache.get_package_revisions_references(ref)
        :param remote: `Remote` object
        :return: `list` of `dict` with all the results, e.g.,
                    [
                      {
                        "revision": "80b7cbe095ac7f38844b6511e69e453a",
                        "time": "2021-07-20 00:56:25 UTC"
                      }
                    ]
        """
        app = ConanApp(self.conan_api.cache_folder)
        # Let's get all the revisions from a remote server
        if remote:
            results = getattr(app.remote_manager, getter_name)(ref, remote=remote)
        else:
            # Let's get the revisions from the local cache
            prefs = getattr(app.cache, getter_name)(ref)
            results = []
            for pref in prefs:
                if getter_name == "get_recipe_revisions_references":
                    timestamp = app.cache.get_recipe_timestamp(pref)
                else:
                    timestamp = app.cache.get_package_timestamp(pref)
                pref.timestamp = timestamp
                results.append(pref)
        return results

    @api_method
    def get_package_revisions_references(self, reference, remote=None):
        """
        Get all the package revisions given a reference from cache or remote.

        :param reference: `PkgReference` without the revision
        :param remote: `Remote` object
        :return: `list` of `dict` with all the results, e.g.,
                    [
                      {
                        "revision": "80b7cbe095ac7f38844b6511e69e453a",
                        "time": "2021-07-20 00:56:25 UTC"
                      }
                    ]
        """
        # Method name to get remotely/locally the revisions
        getter_name = 'get_package_revisions_references'
        return self._get_revisions(reference, getter_name, remote=remote)

    @api_method
    def get_recipe_revisions_references(self, reference, remote=None):
        """
        Get all the recipe revisions given a reference from cache or remote.

        :param reference: `RecipeReference` without the revision
        :param remote: `Remote` object
        :return: `list` of `dict` with all the results, e.g.,
                  [
                      {
                        "revision": "80b7cbe095ac7f38844b6511e69e453a",
                        "time": "2021-07-20 00:56:25 UTC"
                      }
                  ]
        """
        # Method name to get remotely/locally the revisions
        getter_name = 'get_recipe_revisions_references'
        return self._get_revisions(reference, getter_name, remote=remote)

    @api_method
    def get_package_references(self, reference, remote=None):
        """
        Get all the Package IDs given a recipe revision from cache or remote.

        Note: if reference does not have the revision, we'll return the Package IDs for
        the latest recipe revision by default

        :param reference: `RecipeReference` with/without revision
        :param remote: `Remote` object
        :return: `dict` with the reference revision and the results with the package_id as keys, e.g.
                  {
                    "reference": "libcurl/7.77.0#2a9c4fcc8d76d891e4db529efbe24242",
                    "results": {
                        "d5f16437dd4989cc688211b95c24525589acaafd": {
                            "settings": {"compiler": "apple-clang",...},
                            "options": {'options': {'shared': 'False',...}},
                            "requires": ['mylib/1.0.8:3df6ebb8a308d309e882b21988fd9ea103560e16',...]
                        }
                    }
                  }
        """
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            rrev, _ = reference, None if reference.revision else \
                app.remote_manager.get_latest_recipe_reference(reference, remote)
            packages_props = app.remote_manager.search_packages(remote, rrev, None)
        else:
            rrev = reference if reference.revision else app.cache.get_latest_rrev(reference)
            package_ids = app.cache.get_package_references(rrev)
            package_layouts = []
            for pkg in package_ids:
                latest_prev = app.cache.get_latest_prev(pkg)
                package_layouts.append(app.cache.pkg_layout(latest_prev))
            packages_props = search_packages(package_layouts, None)

        return {
            "reference": rrev,
            "results": packages_props
        }
