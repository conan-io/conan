from collections import OrderedDict

from conans.client.graph.graph import BINARY_SKIP
from conans.model.requires import Requirement
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.ref import ConanFileReference


class UserRequirementsDict(object):
    """ user facing dict to allow access of dependencies by name
    """
    def __init__(self, data, require_filter=None):
        self._data = data  # dict-like
        self._require_filter = require_filter  # dict {trait: value} for requirements

    def filter(self, require_filter):
        def filter_fn(require):
            for k, v in require_filter.items():
                if getattr(require, k) != v:
                    return False
            return True
        data = OrderedDict((k, v) for k, v in self._data.items() if filter_fn(k))
        return UserRequirementsDict(data, require_filter)

    def __bool__(self):
        return bool(self._data)

    def _get_require(self, ref, **kwargs):
        assert isinstance(ref, str)
        if "/" in ref:
            ref = ConanFileReference.loads(ref)
        else:
            ref = ConanFileReference(ref, "unknown", "unknown", "unknown", validate=False)

        if self._require_filter:
            kwargs.update(self._require_filter)
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
        # TODO: Probably the BINARY_SKIP should be filtered later at the user level, not forced here
        d = OrderedDict((require, ConanFileInterface(transitive.node.conanfile))
                        for require, transitive in node.transitive_deps.items()
                        if transitive.node.binary != BINARY_SKIP)
        return ConanFileDependencies(d)

    def filter(self, require_filter):
        # FIXME: Copy of hte above, to return ConanFileDependencies class object
        def filter_fn(require):
            for k, v in require_filter.items():
                if getattr(require, k) != v:
                    return False
            return True

        data = OrderedDict((k, v) for k, v in self._data.items() if filter_fn(k))
        return ConanFileDependencies(data, require_filter)

    @property
    def topological_sort(self):
        # Return first independent nodes, final ones are the more direct deps
        result = OrderedDict()
        opened = self._data.copy()

        while opened:
            opened_values = set(opened.values())
            new_opened = OrderedDict()
            for req, conanfile in opened.items():
                deps_in_opened = any(d in opened_values for d in conanfile.dependencies.values())
                if deps_in_opened:
                    new_opened[req] = conanfile  # keep it for next iteration
                else:
                    result[req] = conanfile  # No dependencies in open set!

            opened = new_opened
        return ConanFileDependencies(result)

    @property
    def direct_host(self):
        return self.filter({"build": False, "direct": True, "test": False})

    @property
    def direct_build(self):
        return self.filter({"build": True, "direct": True, "run": True})

    @property
    def host(self):
        return self.filter({"build": False, "test": False})

    @property
    def test(self):
        return self.filter({"build": False, "test": True})

    @property
    def build(self):
        return self.filter({"build": True, "run": True})
