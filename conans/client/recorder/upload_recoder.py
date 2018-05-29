from collections import namedtuple, OrderedDict
from datetime import datetime


class _UploadRecipe(namedtuple("UploadRecipe", "reference, remote_name, remote_url, time")):

    def __new__(cls, reference, remote_name, remote_url):
        the_time = datetime.utcnow()
        return super(cls, _UploadRecipe).__new__(cls, reference, remote_name, remote_url, the_time)

    def to_dict(self):
        return {"id": self.reference, "remote_name": self.remote_name,
                "remote_url": self.remote_url, "time": self.time}


class _UploadPackage(namedtuple("UploadPackage", "package_id, time")):

    def __new__(cls, package_id):
        the_time = datetime.utcnow()
        return super(cls, _UploadPackage).__new__(cls, package_id, the_time)

    def to_dict(self):
        return {"id": self.package_id, "time": self.time}


class UploadRecorder(object):

    def __init__(self):
        self.error = False
        self._info = OrderedDict()

    def add_recipe(self, reference, remote_name, remote_url):
        self._info[reference] = {"recipe": _UploadRecipe(reference, remote_name, remote_url),
                                 "packages": []}

    def add_package(self, reference, package_id):
        self._info[reference]["packages"].append(_UploadPackage(package_id))

    def get_info(self):
        info = {"error": self.error, "uploaded": []}

        for item in self._info.values():
            recipe_info = item["recipe"].to_dict()
            packages_info = [package.to_dict() for package in item["packages"]]
            info["uploaded"].append({"recipe": recipe_info, "packages": packages_info})

        return info
