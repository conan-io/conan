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
        if ref.revision is not None:
            old_package_ids = self._requires.pop(ref, None)  # Get existing one
            if old_package_ids is not None:
                if package_ids is not None:
                    package_ids = old_package_ids.update(package_ids)
                else:
                    package_ids = old_package_ids
            self._requires[ref] = package_ids
        else:  # Manual addition of something without revision
            existing = {r: r for r in self._requires}.get(ref)
            if existing and existing.revision is not None:
                raise ConanException(f"Cannot add {ref} to lockfile, already exists")
            self._requires[ref] = package_ids

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
        self._alias = {}
        self.partial = False

        if deps_graph is None:
            return

        self.update_lock(deps_graph, lock_packages)

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

        self._alias.update(deps_graph.aliased)

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
        """ adding new things manually will trigger the sort() of the locked list, so lockfiles
        alwasys keep the ordered lists. This means that for some especial edge cases it might
        be necessary to allow removing from a lockfile, for example to test an older version
        than the one locked (in general adding works better for moving forward to newer versions)
        """
        if requires:
            for r in requires:
                self._requires.add(r)
            self._requires.sort()
        if build_requires:
            for r in build_requires:
                self._build_requires.add(r)
            self._build_requires.sort()
        if python_requires:
            for r in python_requires:
                self._python_requires.add(r)
            self._python_requires.sort()

    @staticmethod
    def deserialize(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = Lockfile()
        version = data.get("version")
        if version and version != LOCKFILE_VERSION:
            raise ConanException("This lockfile was created with an incompatible "
                                 "version. Please regenerate the lockfile")
        if "requires" in data:
            graph_lock._requires = _LockRequires.deserialize(data["requires"])
        if "build_requires" in data:
            graph_lock._build_requires = _LockRequires.deserialize(data["build_requires"])
        if "python_requires" in data:
            graph_lock._python_requires = _LockRequires.deserialize(data["python_requires"])
        if "alias" in data:
            graph_lock._alias = {RecipeReference.loads(k): RecipeReference.loads(v)
                                 for k, v in data["alias"].items()}
        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        result = {"version": LOCKFILE_VERSION}
        if self._requires:
            result["requires"] = self._requires.serialize()
        if self._build_requires:
            result["build_requires"] = self._build_requires.serialize()
        if self._python_requires:
            result["python_requires"] = self._python_requires.serialize()
        if self._alias:
            result["alias"] = {repr(k): repr(v) for k, v in self._alias.items()}
        return result

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
        version_range = require.version_range
        ref = require.ref
        matches = [r for r in locked_refs if r.name == ref.name and r.user == ref.user and
                   r.channel == ref.channel]
        if version_range:
            for m in matches:
                if m.version in version_range:
                    require.ref = m
                    break
            else:
                if not self.partial:
                    raise ConanException(f"Requirement '{ref}' not in lockfile")
        else:
            alias = require.alias
            if alias:
                locked_alias = self._alias.get(alias)
                if locked_alias is not None:
                    require.ref = locked_alias
                elif not self.partial:
                    raise ConanException(f"Requirement alias '{alias}' not in lockfile")
            ref = require.ref
            if ref.revision is None:
                for m in matches:
                    if m.version == ref.version:
                        require.ref = m
                        break
                else:
                    if not self.partial:
                        raise ConanException(f"Requirement '{ref}' not in lockfile")
            else:
                if ref not in matches and not self.partial:
                    raise ConanException(f"Requirement '{repr(ref)}' not in lockfile")

    def resolve_locked_pyrequires(self, require):
        locked_refs = self._python_requires.refs()  # CHANGE
        self._resolve(require, locked_refs)
