from collections import OrderedDict

from conans.client.graph.graph import CONTEXT_BUILD
from conans.model.conanfile_interface import ConanFileInterface
from conans.model.ref import ConanFileReference


class Requirement(object):

    def __init__(self, ref, build=False, direct=True, test=False):
        # By default this is a generic library requirement
        self.ref = ref
        self.build = build  # This dependent node is a build tool that is executed at build time only
        self.direct = direct
        self.test = test

    def __repr__(self):
        return repr(self.__dict__)

    def __hash__(self):
        return hash((self.ref.name, self.build))

    def __eq__(self, other):
        return self.ref.name == other.ref.name and self.build == other.build

    def __ne__(self, other):
        return not self.__eq__(other)


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

    __nonzero__ = __bool__

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
        # TODO: This construction will be easier in 2.0
        build, test, host = [], [], []
        for edge in node.dependencies:
            if edge.build_require:
                if not edge.require.force_host_context:
                    build.append(edge.dst)
                else:
                    test.append(edge.dst)
            else:
                host.append(edge.dst)

        d = OrderedDict()

        def expand(nodes, is_build, is_test):
            all_nodes = set(nodes)
            for n in nodes:
                conanfile = ConanFileInterface(n.conanfile)
                d[Requirement(n.ref, build=is_build, test=is_test)] = conanfile

            next_nodes = nodes
            while next_nodes:
                new_nodes = []
                for next_node in next_nodes:
                    for e in next_node.dependencies:
                        if not e.build_require and not e.private and e.dst not in all_nodes:
                            new_nodes.append(e.dst)
                            all_nodes.add(e.dst)
                next_nodes = new_nodes
                for n in next_nodes:
                    conanfile = ConanFileInterface(n.conanfile)
                    d[Requirement(n.ref, build=is_build, test=is_test, direct=False)] = conanfile

        expand(host, is_build=False, is_test=False)
        expand(build, is_build=True, is_test=False)
        expand(test, is_build=False, is_test=True)

        return ConanFileDependencies(d)

    def filter(self, require_filter):
        return super(ConanFileDependencies, self).filter(require_filter)

    @property
    def direct_host(self):
        return self.filter({"build": False, "direct": True, "test": False})

    @property
    def direct_build(self):
        return self.filter({"build": True, "direct": True})

    @property
    def host(self):
        return self.filter({"build": False, "test": False})

    @property
    def test(self):
        return self.filter({"build": False, "test": True})

    @property
    def build(self):
        return self.filter({"build": True})
