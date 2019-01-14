from collections import OrderedDict, namedtuple


class _SearchRecipe(namedtuple("SearchRecipe", "ref")):
    with_packages = True

    def to_dict(self):
        data = {"id": str(self.ref)}
        return data


class _SearchPackage(namedtuple("SearchPackage",
                                "package_id, options, settings, requires, outdated")):

    def to_dict(self):
        return {"id": self.package_id, "options": self.options, "settings": self.settings,
                "requires": self.requires, "outdated": self.outdated}


class SearchRecorder(object):

    def __init__(self):
        self.error = False
        self.keyword = "results"
        self._info = OrderedDict()

    def add_recipe(self, remote_name, ref, with_packages=True):
        recipe = _SearchRecipe(ref)
        recipe.with_packages = with_packages
        if remote_name not in self._info:
            self._info[remote_name] = OrderedDict()
        self._info[remote_name][ref.full_repr()] = {"recipe": recipe, "packages": []}

    def add_package(self, remote_name, ref, package_id, options, settings, requires, outdated):
        sp = _SearchPackage(package_id, options, settings, requires, outdated)
        self._info[remote_name][ref.full_repr()]["packages"].append(sp)

    def get_info(self):
        info = {"error": self.error, self.keyword: []}

        for remote_name, recipe_packages in sorted(self._info.items()):
            remote_info = {"remote": remote_name, "items": []}
            for item in recipe_packages.values():
                recipe_info = item["recipe"].to_dict()
                if item["recipe"].with_packages:
                    packages_info = [package.to_dict() for package in item["packages"]]
                    remote_info["items"].append({"recipe": recipe_info, "packages": packages_info})
                else:
                    remote_info["items"].append({"recipe": recipe_info})
            info[self.keyword].append(remote_info)
        return info
