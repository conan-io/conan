from collections import namedtuple, OrderedDict


class _SearchRecipe(namedtuple("SearchRecipe", "reference")):
    with_packages = True

    def __new__(cls, reference):
        return super(cls, _SearchRecipe).__new__(cls, reference)

    def to_dict(self):
        return {"id": self.reference}


class _SearchPackage(namedtuple("SearchPackage", "package_id, options, settings, requires, outdated")):

    def __new__(cls, package_id, options, settings, requires, outdated):
        return super(cls, _SearchPackage).__new__(cls, package_id, options, settings, requires, outdated)

    def to_dict(self):
        return {"id": self.package_id, "options": self.options, "settings": self.settings,
                "requires": self.requires, "outdated": self.outdated}


class SearchRecoder(object):

    def __init__(self):
        self.error = False
        self._info = OrderedDict()

    def add_recipe(self, reference, with_packages=True):
        recipe = _SearchRecipe(reference)
        recipe.with_packages = with_packages
        self._info[reference] = {"recipe": recipe, "packages": []}

    def add_package(self, reference, package_id, options, settings, requires, outdated):
        self._info[reference]["packages"].append(_SearchPackage(package_id, options, settings,
                                                                requires, outdated))

    def get_info(self):
        info = {"error": self.error, "found": []}

        for item in self._info.values():
            recipe_info = item["recipe"].to_dict()
            if item["recipe"].with_packages:
                packages_info = [package.to_dict() for package in item["packages"]]
                info["found"].append({"recipe": recipe_info, "packages": packages_info})
            else:
                info["found"].append({"recipe": recipe_info})
        return info
