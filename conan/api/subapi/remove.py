from typing import Optional

from conan.api.model import Remote
from conan.api.model import PkgReference
from conan.api.model import RecipeReference


class RemoveAPI:

    def __init__(self, conan_api, api_helpers):
        self._conan_api = conan_api
        self._api_helpers = api_helpers

    def recipe(self, ref: RecipeReference, remote: Optional[Remote] = None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes the recipe (or recipe revision if present) and all the packages (with all prev)"""

        if remote:
            self._api_helpers.remote_manager.remove_recipe(ref, remote)
        else:
            self.all_recipe_packages(ref)
            recipe_layout = self._api_helpers.cache.recipe_layout(ref)
            self._api_helpers.cache.remove_recipe_layout(recipe_layout)

    def all_recipe_packages(self, ref: RecipeReference, remote: Optional[Remote] = None):
        assert ref.revision, "Recipe revision cannot be None to remove a recipe"
        """Removes all the packages from the provided reference"""

        if remote:
            self._api_helpers.remote_manager.remove_all_packages(ref, remote)
        else:
            # Remove all the prefs with all the prevs
            self._remove_all_local_packages(ref)

    def _remove_all_local_packages(self, ref):
        # Get all the prefs and all the prevs
        pkg_ids = self._api_helpers.cache.get_package_references(ref, only_latest_prev=False)
        for pref in pkg_ids:
            package_layout = self._api_helpers.cache.pkg_layout(pref)
            self._api_helpers.cache.remove_package_layout(package_layout)

    def package(self, pref: PkgReference, remote: Optional[Remote]):
        assert pref.ref.revision, "Recipe revision cannot be None to remove a package"
        assert pref.revision, "Package revision cannot be None to remove a package"

        if remote:
            # FIXME: Create a "packages" method to optimize remote remove?
            self._api_helpers.remote_manager.remove_packages([pref], remote)
        else:
            package_layout = self._api_helpers.cache.pkg_layout(pref)
            self._api_helpers.cache.remove_package_layout(package_layout)
