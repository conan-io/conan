from conans.model.ref import ConanFileReference
from conans.model.info import ConanInfo
import json


class SearchInfo(dict):
    """ {ConanFileReference: dict{package_id: ConanInfo}
    """

    def serialize(self):
        serialize_info = {}
        for ref, conan_info in self.iteritems():
            serialize_info[repr(ref)] = {k: v.serialize() for k, v in conan_info.iteritems()}
        return serialize_info

    @staticmethod
    def deserialize(data):
        tmp = json.loads(data)
        ret = SearchInfo()
        for conan_ref, packages in tmp.iteritems():
            conan_ref = ConanFileReference.loads(conan_ref)
            ret[conan_ref] = {}
            for package_id, info in packages.iteritems():
                ret[conan_ref][package_id] = ConanInfo.deserialize(info)

        return ret
