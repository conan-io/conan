from typing import Dict

from conans.cli.api.model import Remote, PkgConfiguration
from conans.cli.conan_app import ConanApp
from conans.errors import NotFoundException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.search import get_packages_search_info, filter_packages


class ListAPI:
    """
    Get references from the recipes and packages in the cache or a remote
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def latest_recipe_revision(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "latest_recipe_revision: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
        else:
            ret = app.cache.get_latest_recipe_reference(ref)

        return ret

    def recipe_revisions(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "recipe_revisions: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            results = app.remote_manager.get_recipe_revisions_references(ref, remote=remote)
        else:
            results = app.cache.get_recipe_revisions_references(ref, only_latest_rrev=False)

        return results

    def latest_package_revision(self, pref: PkgReference, remote=None):
        assert pref.revision is None, "latest_package_revision: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_package_reference(pref, remote=remote)
        else:
            ret = app.cache.get_latest_package_reference(pref)

        return ret

    def package_revisions(self, pref: PkgReference, remote: Remote=None):
        assert pref.ref.revision is not None, "package_revisions requires a recipe revision, " \
                                              "check latest first if needed"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            results = app.remote_manager.get_package_revisions_references(pref, remote=remote)
        else:
            refs = app.cache.get_package_revisions_references(pref, only_latest_prev=False)
            results = []
            for ref in refs:
                # TODO: Why another call, and why get_package_revisions_references doesn't return
                #  already the timestamps?
                timestamp = app.cache.get_package_timestamp(ref)
                ref.timestamp = timestamp
                results.append(ref)
        return results

    def packages_configurations(self, ref: RecipeReference,
                                remote=None) -> Dict[PkgReference, PkgConfiguration]:
        assert ref.revision is not None, "packages: ref should have a revision. " \
                                         "Check latest if needed."
        if not remote:
            app = ConanApp(self.conan_api.cache_folder)
            prefs = app.cache.get_package_references(ref)
            packages = get_packages_search_info(app.cache, prefs)
            results = {pref: PkgConfiguration(data) for pref, data in packages.items()}
        else:
            app = ConanApp(self.conan_api.cache_folder)
            packages = app.remote_manager.search_packages(remote, ref)
            results = {pref: PkgConfiguration(data) for pref, data in packages.items()}
        return results

    def filter_packages_configurations(self, pkg_configurations, query):
        """
        :param pkg_configurations: Dict[PkgReference, PkgConfiguration]
        :param query: str like "os=Windows AND (arch=x86 OR compiler=gcc)"
        :return: Dict[PkgReference, PkgConfiguration]
        """
        return filter_packages(query, pkg_configurations)
