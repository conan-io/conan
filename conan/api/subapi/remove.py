from conan.api.model import Remote
from conan.api.subapi import api_method
from conan.internal.conan_app import ConanApp
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference


class RemoveAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @api_method
    def recipe(self, ref: RecipeReference, remote: Remote=None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes the recipe (or recipe revision if present) and all the packages (with all prev)"""
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            app.remote_manager.remove_recipe(ref, remote)
        else:
            self.all_recipe_packages(ref)
            recipe_layout = app.cache.ref_layout(ref)
            app.cache.remove_recipe_layout(recipe_layout)

    @api_method
    def all_recipe_packages(self, ref: RecipeReference, remote: Remote = None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes all the packages from the provided reference"""
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            app.remote_manager.remove_all_packages(ref, remote)
        else:
            # Remove all the prefs with all the prevs
            self._remove_all_local_packages(app, ref)

    @staticmethod
    def _remove_all_local_packages(app, ref):
        # Get all the prefs and all the prevs
        pkg_ids = app.cache.get_package_references(ref)
        all_package_revisions = []
        for pkg_id in pkg_ids:
            all_package_revisions.extend(app.cache.get_package_revisions_references(pkg_id))
        for pref in all_package_revisions:
            package_layout = app.cache.pkg_layout(pref)
            app.cache.remove_package_layout(package_layout)

    @api_method
    def package(self, pref: PkgReference, remote: Remote):
        assert pref.ref.revision, "Recipe revision cannot be None to remove a package"
        assert pref.revision, "Package revision cannot be None to remove a package"

        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            # FIXME: Create a "packages" method to optimize remote remove?
            app.remote_manager.remove_packages([pref], remote)
        else:
            package_layout = app.cache.pkg_layout(pref)
            app.cache.remove_package_layout(package_layout)
