from conans.cli.api.model import Remote
from conans.cli.conan_app import ConanApp
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference

# FIXME: The name "references" is not good either, I'm sure we will find a
#        better name when we complete the API with other "primitives"


class ReferencesAPI:
    """
    Get references from the recipes and packages in the cache or a remote
    """

    def __init__(self, conan_api):
        self.conan_api = conan_api

    def latest_recipe(self, ref: RecipeReference, remote: Remote=None) -> RecipeReference:
        assert ref.revision is None, "lastest_recipe_reference: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_recipe_reference(ref, remote=remote)
        else:
            ret = app.cache.get_latest_recipe_reference(ref)

        return ret

    def latest_package(self, pref: PkgReference, remote: Remote=None) -> PkgReference:
        assert pref.ref.revision is not None, "latest_package_reference: the recipe revision is None"
        assert pref.revision is None, "latest_package_reference: "
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            ret = app.remote_manager.get_latest_package_reference(pref, remote=remote)
        else:
            ret = app.cache.get_latest_package_reference(pref)
        return ret

    def recipe_revisions(self, ref: RecipeReference, remote=None):
        assert ref.revision is None, "recipe_revisions: ref already have a revision"
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            results = app.remote_manager.get_recipe_revisions_references(ref, remote=remote)
        else:
            results = app.cache.get_recipe_revisions_references(ref, only_latest_rrev=False)

        return results

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
                timestamp = app.cache.get_package_timestamp(ref)
                ref.timestamp = timestamp
                results.append(ref)
        return results
