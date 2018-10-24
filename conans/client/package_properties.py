import json


class PackageProperties(object):

    def __init__(self, recipe_revision):
        self.recipe_revision = recipe_revision

    @staticmethod
    def loads(contents):
        data = json.loads(contents)
        ret = PackageProperties(data["recipe_revision"])
        return ret

    def dumps(self):
        return json.dumps({"recipe_revision": self.recipe_revision})
