from typing import Optional

from conan.api.model import Remote
from conan.internal.conan_app import ConanBasicApp
from conan.api.model import PkgReference
from conan.api.model import RecipeReference


class RemoveAPI:

    def __init__(self, conan_api):
        self._conan_api = conan_api

    def recipe(self, ref: RecipeReference, remote: Optional[Remote] = None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes the recipe (or recipe revision if present) and all the packages (with all prev)"""
        app = ConanBasicApp(self._conan_api)
        if remote:
            app.remote_manager.remove_recipe(ref, remote)
        else:
            self.all_recipe_packages(ref)
            recipe_layout = app.cache.recipe_layout(ref)
            app.cache.remove_recipe_layout(recipe_layout)

    def all_recipe_packages(self, ref: RecipeReference, remote: Optional[Remote] = None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes all the packages from the provided reference"""
        app = ConanBasicApp(self._conan_api)
        if remote:
            app.remote_manager.remove_all_packages(ref, remote)
        else:
            # Remove all the prefs with all the prevs
            self._remove_all_local_packages(app, ref)

    @staticmethod
    def _remove_all_local_packages(app, ref):
        from conan.internal.errors import ConanReferenceDoesNotExistInDB
        # Get all the prefs and all the prevs
        pkg_ids = app.cache.get_package_references(ref, only_latest_prev=False)
        for pref in pkg_ids:
            try:
                package_layout = app.cache.pkg_layout(pref)
                app.cache.remove_package_layout(package_layout)
            except ConanReferenceDoesNotExistInDB:
                # Package already removed by another process - this is fine
                pass

    def package(self, pref: PkgReference, remote: Optional[Remote]):
        from conan.internal.errors import ConanReferenceDoesNotExistInDB
        assert pref.ref.revision, "Recipe revision cannot be None to remove a package"
        assert pref.revision, "Package revision cannot be None to remove a package"

        app = ConanBasicApp(self._conan_api)
        if remote:
            # FIXME: Create a "packages" method to optimize remote remove?
            app.remote_manager.remove_packages([pref], remote)
        else:
            try:
                package_layout = app.cache.pkg_layout(pref)
                app.cache.remove_package_layout(package_layout)
            except ConanReferenceDoesNotExistInDB:
                # Package already removed by another process - this is fine
                # The goal was to remove it, and it's already gone
                pass
