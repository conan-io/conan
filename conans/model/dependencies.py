from collections import OrderedDict

from conans.client.graph.graph import BINARY_SKIP
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirement


class UserRequirementsDict(object):
    """ user facing dict to allow access of dependencies by name
    """
    def __init__(self, data):
        self._data = data  # dict-like

    def filter(self, filter_fn):
        data = OrderedDict((k, v) for k, v in self._data.items() if filter_fn(k, v))
        return UserRequirementsDict(data)

    @staticmethod
    def _get_require(ref, **kwargs):
        assert isinstance(ref, str)
        if "/" in ref:
            ref = ConanFileReference.loads(ref)
        else:
            ref = ConanFileReference(ref, "unknown", "unknown", "unknown", validate=False)
        r = Requirement(ref, **kwargs)
        return r

    def get(self, ref, **kwargs):
        r = self._get_require(ref, **kwargs)
        return self._data.get(r)

    def __getitem__(self, name):
        r = self._get_require(name)
        return self._data[r]

    def __delitem__(self, name):
        r = self._get_require(name)
        del self._data[r]

    def items(self):
        return self._data.items()

    def values(self):
        return self._data.values()


class ConanFileDependencies(UserRequirementsDict):

    @staticmethod
    def from_node(node):
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in node.transitive_deps.items()
                        if transitive.node.binary != BINARY_SKIP)
        return ConanFileDependencies(d)

    def filter(self, filter_fn):
        return super(ConanFileDependencies, self).filter(filter_fn)

    @property
    def direct_host_requires(self):
        return self.filter(lambda r, c: r.direct and not r.build)

    @property
    def direct_build_requires(self):
        return self.filter(lambda r, c: r.direct and r.build)

    @property
    def host_requires(self):
        return self.filter(lambda r, c: not r.build)

    @property
    def build_requires(self):
        return self.filter(lambda r, c: r.build)
