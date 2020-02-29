from collections import OrderedDict, namedtuple
from datetime import datetime

from conans.model.ref import ConanFileReference


class _UploadElement(namedtuple("UploadElement", "reference, remote_name, remote_url, time")):

    def __new__(cls, reference, remote_name, remote_url):
        the_time = datetime.utcnow()
        return super(cls, _UploadElement).__new__(cls, reference, remote_name, remote_url, the_time)

    def to_dict(self):
        ret = {"remote_name": self.remote_name,
               "remote_url": self.remote_url, "time": self.time}
        ret.update(_id_dict(self.reference))
        return ret


def _id_dict(ref):
    if isinstance(ref, ConanFileReference):
        ret = {"id": str(ref)}
    else:
        ret = {"id": ref.id}

    # FIXME: When revisions feature is completely release this field should be always there
    # with None if needed
    if ref.revision:
        ret["revision"] = ref.revision
    return ret


class UploadRecorder(object):

    def __init__(self):
        self.error = False
        self._info = OrderedDict()

    def add_recipe(self, ref, remote_name, remote_url):

        self._info[repr(ref.copy_clear_rev())] = {"recipe": _UploadElement(ref, remote_name, remote_url),
                                "packages": []}

    def add_package(self, pref, remote_name, remote_url):
        self._info[repr(pref.ref.copy_clear_rev())]["packages"].append(_UploadElement(pref, remote_name, remote_url))

    def get_info(self):
        info = {"error": self.error, "uploaded": []}

        for item in self._info.values():
            recipe_info = item["recipe"].to_dict()
            packages_info = [package.to_dict() for package in item["packages"]]
            info["uploaded"].append({"recipe": recipe_info, "packages": packages_info})

        return info
