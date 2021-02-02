from conans.model.ref import PackageReference


class PackageLayout:
    def __init__(self, recipe_layout: 'RecipeLayout', pref: PackageReference):
        self._recipe_layout = recipe_layout
        self._pref = pref
