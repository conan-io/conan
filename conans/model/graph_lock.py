import json
import os
from collections import OrderedDict

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER, CONTEXT_BUILD
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load, save

LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.5"


class _LockRequires:
    """
    This is an ordered set of locked references.
    It is implemented this way to allow adding package_id:prev information later,
    otherwise it could be a bare list
    """
    def __init__(self):
        self._requires = OrderedDict()  # {require: package_ids}

    def __contains__(self, item):
        return item in self._requires

    def refs(self):
        return self._requires.keys()

    def get(self, item):
        return self._requires.get(item)

    def serialize(self):
        result = []
        for k, v in self._requires.items():
            if v is None:
                result.append(repr(k))
            else:
                result.append((repr(k), v))
        return result

    @staticmethod
    def deserialize(data):
        result = _LockRequires()
        for d in data:
            if isinstance(d, str):
                result._requires[RecipeReference.loads(d)] = None
            else:
                result._requires[RecipeReference.loads(d[0])] = d[1]
        return result

    def add(self, ref, package_ids=None):
        # In case we have an existing, incomplete thing
        pop_ref = RecipeReference.loads(str(ref))
        self._requires.pop(pop_ref, None)
        if package_ids is not None:
            self._requires.setdefault(ref, {}).update(package_ids)
        else:
            self._requires.setdefault(ref, None)  # To keep previous packgae_id: prev if exists

    def insert(self, ref):
        self._requires[ref] = None
        self._requires.move_to_end(ref, last=False)

    def sort(self):
        self._requires = OrderedDict(reversed(sorted(self._requires.items())))

    def merge(self, other):
        """
        :type other: _LockRequires
        """
        # TODO: What happens when merging incomplete refs? Probably str(ref) should be used
        for k, v in other._requires.items():
            if k in self._requires:
                if v is not None:
                    self._requires.setdefault(k, {}).update(v)
            else:
                self._requires[k] = v
        self.sort()


class Lockfile(object):

    def __init__(self, deps_graph=None, lock_packages=False):
        self._requires = _LockRequires()
        self._python_requires = _LockRequires()
        self._build_requires = _LockRequires()
        self.alias = {}  # TODO: Alias locking needs to be tested more
        self.strict = False

        if deps_graph is None:
            return

        self.update_lock(deps_graph, lock_packages)
        self.alias = deps_graph.aliased

    def update_lock(self, deps_graph, lock_packages=False):
        for graph_node in deps_graph.nodes:
            try:
                for r in graph_node.conanfile.python_requires.all_refs():
                    self._python_requires.add(r)
            except AttributeError:
                pass
            if graph_node.recipe in (RECIPE_VIRTUAL, RECIPE_CONSUMER) or graph_node.ref is None:
                continue
            assert graph_node.conanfile is not None

            pids = {graph_node.package_id: graph_node.prev} if lock_packages else None
            if graph_node.context == CONTEXT_BUILD:
                self._build_requires.add(graph_node.ref, pids)
            else:
                self._requires.add(graph_node.ref, pids)

        self._requires.sort()
        self._build_requires.sort()
        self._python_requires.sort()

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        if not os.path.isfile(path):
            raise ConanException("Missing lockfile in: %s" % path)
        content = load(path)
        try:
            return Lockfile.loads(content)
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(path, e))

    @staticmethod
    def loads(content):
        return Lockfile.deserialize(json.loads(content))

    def dumps(self):
        return json.dumps(self.serialize(), indent=4)

    def save(self, path):
        save(path, self.dumps())

    def merge(self, other):
        """
        :type other: Lockfile
        """
        self._requires.merge(other._requires)
        self._build_requires.merge(other._build_requires)
        self._python_requires.merge(other._python_requires)

    def add(self, requires=None, build_requires=None, python_requires=None):
        if requires:
            for r in requires:
                self._requires.add(r)
        if build_requires:
            for r in build_requires:
                self._build_requires.add(r)
        if python_requires:
            for r in python_requires:
                self._python_requires.add(r)

    @staticmethod
    def deserialize(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = Lockfile()
        version = data.get("version")
        if version and version != LOCKFILE_VERSION:
            raise ConanException("This lockfile was created with an incompatible "
                                 "version. Please regenerate the lockfile")
        graph_lock._requires = _LockRequires.deserialize(data["requires"])
        graph_lock._build_requires = _LockRequires.deserialize(data["build_requires"])
        graph_lock._python_requires = _LockRequires.deserialize(data["python_requires"])
        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        return {"version": LOCKFILE_VERSION,
                "requires": self._requires.serialize(),
                "build_requires": self._build_requires.serialize(),
                "python_requires": self._python_requires.serialize()
                }

    def resolve_locked(self, node, require):
        if require.build or node.context == CONTEXT_BUILD:
            locked_refs = self._build_requires.refs()
        else:
            locked_refs = self._requires.refs()
        self._resolve(require, locked_refs)

    def resolve_prev(self, node):
        if node.context == CONTEXT_BUILD:
            prevs = self._build_requires.get(node.ref)
        else:
            prevs = self._requires.get(node.ref)
        if prevs:
            return prevs.get(node.package_id)

    def _resolve(self, require, locked_refs):
        ref = require.ref
        version_range = require.version_range

        if version_range:
            matches = [r for r in locked_refs if r.name == ref.name and r.user == ref.user and
                       r.channel == ref.channel]
            for m in matches:
                if m.version in version_range:
                    require.ref = m
                    break
            else:
                if self.strict:
                    raise ConanException(f"Requirement '{ref}' not in lockfile")
        else:
            alias = require.alias
            if alias:
                require.ref = self.alias.get(require.ref, require.ref)
            elif require.ref.revision is None:
                for r in locked_refs:
                    if r.name == ref.name and r.version == ref.version and r.user == ref.user and \
                            r.channel == ref.channel:
                        require.ref = r
                        break
                else:
                    if self.strict:
                        raise ConanException(f"Requirement '{ref}' not in lockfile")
            else:
                if ref not in locked_refs and self.strict:
                    raise ConanException(f"Requirement '{repr(ref)}' not in lockfile")

    def resolve_locked_pyrequires(self, require):
        locked_refs = self._python_requires.refs()  # CHANGE
        self._resolve(require, locked_refs)

    def update_lock_export_ref(self, ref):
        """ when the recipe is exported, it will complete the missing RREV, otherwise it should
        match the existing RREV
        """
        # Filter existing matching
        if ref not in self._requires:
            # It is inserted in the first position, because that will result in prioritization
            # That includes testing previous versions in a version range
            self._requires.insert(ref)
