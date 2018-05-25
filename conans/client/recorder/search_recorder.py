from collections import namedtuple, OrderedDict


class _SearchRecipe(namedtuple("SearchRecipe", "reference, recipe_hash")):

    def to_dict(self):
        data = {"id": self.reference}
        if self.recipe_hash:
            data["hash"] = self.recipe_hash
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

    def add_recipe(self, remote, reference, recipe_hash):
        recipe = _SearchRecipe(reference, recipe_hash)
        if remote not in self._info:
            self._info[remote] = OrderedDict()
        self._info[remote][reference] = {"recipe": recipe, "packages": []}

    def add_package(self, remote, reference, package_id, options, settings, requires, outdated):
        self._info[remote][reference]["packages"].append(_SearchPackage(package_id, options,
                                                                        settings, requires,
                                                                        outdated))

    def get_info(self):
        info = {"error": self.error, self.keyword: []}

        for remote, recipe_pacakges in sorted(self._info.items()):
            remote_info = {"remote": remote, "items": []}
            for reference, item in recipe_pacakges.items():
                recipe_info = item["recipe"].to_dict()
                if "hash" in recipe_info:
                    packages_info = [package.to_dict() for package in item["packages"]]
                    remote_info["items"].append({"recipe": recipe_info, "packages": packages_info})
                else:
                    remote_info["items"].append({"recipe": recipe_info})
            info[self.keyword].append(remote_info)
        return info
