from conan.cache.recipe_layout import RecipeLayout
from conans.model.ref import ConanFileReference


class Cache:
    def __init__(self, directory: str):
        self._directory = directory

    def get_reference_layout(self, ref: ConanFileReference) -> RecipeLayout:
        # TODO: Lot of things to implement
        return RecipeLayout(self, ref)
