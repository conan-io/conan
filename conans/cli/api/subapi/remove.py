from conans.cli.api.subapi import api_method
from conans.cli.conan_app import ConanApp
from conans.errors import RecipeNotFoundException, ConanException
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.search.search import search_recipes, filter_packages


class RemoveAPI:

    def __init__(self, conan_api):
        self.conan_api = conan_api

    @staticmethod
    def _remove_local_recipe(app, ref):
        if app.cache.installed_as_editable(ref):
            msg = "Package '{r}' is installed as editable, remove it first using " \
                  "command 'conan editable remove {r}'".format(r=ref)
            raise ConanException(msg)
        # Get all the prefs and all the prevs
        pkg_ids = app.cache.get_package_references(ref)
        all_package_revisions = []
        for pkg_id in pkg_ids:
            all_package_revisions.extend(app.cache.get_package_revisions_references(pkg_id))
        for pref in all_package_revisions:
            package_layout = app.cache.pkg_layout(pref)
            app.cache.remove_package_layout(package_layout)
        # Remove the all the prevs too
        refs = app.cache.get_recipe_revisions_references(ref)
        for ref in refs:
            recipe_layout = app.cache.ref_layout(ref)
            app.cache.remove_recipe_layout(recipe_layout)

    @api_method
    def recipe(self, ref: RecipeReference, remote=None):
        """Removes the recipe (or recipe revision if present) and all the packages (with all prev)"""
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            app.remote_manager.remove_recipe(ref, remote)
        else:
            refs = app.cache.get_recipe_revisions_references(ref)
            if not refs:
                raise RecipeNotFoundException(ref)
            for ref in refs:
                # Remove all the prefs with all the prevs
                self._remove_local_recipe(app, ref)

    @api_method
    def package(self, pref: PkgReference, remote=None):
        app = ConanApp(self.conan_api.cache_folder)
        if remote:
            app.remote_manager.remove_packages(pref.p, remote)
        else:
            refs = app.cache.get_recipe_revisions_references(ref)
            if not refs:
                raise RecipeNotFoundException(ref)
            for ref in refs:
                # Remove all the prefs with all the prevs
                self._remove_local_recipe(app, ref)
