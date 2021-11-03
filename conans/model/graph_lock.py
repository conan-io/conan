import json
import os

from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER, CONTEXT_BUILD
from conans.client.graph.range_resolver import range_satisfies
from conans.errors import ConanException
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load, save

LOCKFILE = "conan.lock"
LOCKFILE_VERSION = "0.5"


class Lockfile(object):

    def __init__(self, deps_graph=None):
        self.requires = []
        self.python_requires = []
        self.build_requires = []
        self.alias = {}
        self.strict = False

        if deps_graph is None:
            return

        requires = set()
        python_requires = set()
        build_requires = set()
        for graph_node in deps_graph.nodes:
            try:
                python_requires.update(graph_node.conanfile.python_requires.all_refs())
            except AttributeError:
                pass
            if graph_node.recipe in (RECIPE_VIRTUAL, RECIPE_CONSUMER) or graph_node.ref is None:
                continue
            assert graph_node.conanfile is not None

            if graph_node.context == CONTEXT_BUILD:
                build_requires.add(RecipeReference.from_conanref(graph_node.ref))
            else:
                requires.add(RecipeReference.from_conanref(graph_node.ref))

        # Sorted, newer versions first, so first found is valid for version ranges
        # TODO: Need to impmlement same ordering for revisions, based on revision time
        self.requires = list(reversed(sorted(requires)))
        self.python_requires = list(reversed(sorted(python_requires)))
        self.build_requires = list(reversed(sorted(build_requires)))
        self.alias = deps_graph.aliased

    @staticmethod
    def load(path):
        if not path:
            raise IOError("Invalid path")
        if not os.path.isfile(path):
            raise ConanException("Missing lockfile in: %s" % path)
        content = load(path)
        try:
            return Lockfile.deserialize(json.loads(content))
        except Exception as e:
            raise ConanException("Error parsing lockfile '{}': {}".format(path, e))

    def save(self, path):
        save(path, json.dumps(self.serialize(), indent=True))

    def update_lock(self, deps_graph):
        """ add new things at the beginning, to give more priority
        """
        requires = set()
        build_requires = set()
        for graph_node in deps_graph.nodes:
            if graph_node.recipe in (RECIPE_VIRTUAL, RECIPE_CONSUMER) or graph_node.ref is None:
                continue
            assert graph_node.conanfile is not None

            if graph_node.context == CONTEXT_BUILD:
                build_requires.add(RecipeReference.from_conanref(graph_node.ref))
            else:
                requires.add(RecipeReference.from_conanref(graph_node.ref))

        requires.update(self.requires)
        self.requires = list(reversed(sorted(requires)))
        build_requires.update(self.build_requires)
        self.build_requires = list(reversed(sorted(build_requires)))
        # TODO other members

    def merge(self, other):
        self.requires = list(reversed(sorted(set(other.requires + self.requires))))
        self.build_requires = list(reversed(sorted(set(other.build_requires + self.build_requires))))

    @staticmethod
    def deserialize(data):
        """ constructs a GraphLock from a json like dict
        """
        graph_lock = Lockfile(deps_graph=None)
        version = data.get("version")
        if version and version != LOCKFILE_VERSION:
            raise ConanException("This lockfile was created with an incompatible "
                                 "version. Please regenerate the lockfile")
        for r in data["requires"]:
            graph_lock.requires.append(RecipeReference.loads(r))
        for r in data["python_requires"]:
            graph_lock.python_requires.append(RecipeReference.loads(r))
        for r in data["build_requires"]:
            graph_lock.build_requires.append(RecipeReference.loads(r))
        return graph_lock

    def serialize(self):
        """ returns the object serialized as a dict of plain python types
        that can be converted to json
        """
        return {"version": LOCKFILE_VERSION,
                "requires": [repr(r) for r in self.requires],
                "python_requires": [repr(r) for r in self.python_requires],
                "build_requires": [repr(r) for r in self.build_requires]}

    def resolve_locked(self, node, require):
        ref = require.ref
        if require.build or node.context == CONTEXT_BUILD:
            locked_refs = self.build_requires
        else:
            locked_refs = self.requires
        version_range = require.version_range

        if version_range:
            matches = [r for r in locked_refs if r.name == ref.name and r.user == ref.user and
                       r.channel == ref.channel]
            for m in matches:
                if range_satisfies(version_range, str(m.version)):
                    require.ref = m.to_conanfileref()
                    break
            else:
                if self.strict:
                    raise ConanException(f"Requirement '{ref}' not in lockfile")
        else:
            alias = require.alias
            if alias:
                require.ref = self.alias.get(require.ref, require.ref)
            elif require.ref.revision is None:
                # find exact revision
                pass

    def resolve_locked_pyrequires(self, require):
        ref = require.ref
        locked_refs = self.python_requires  # CHANGE
        version_range = require.version_range
        if version_range:
            matches = [r for r in locked_refs if r.name == ref.name and r.user == ref.user and
                       r.channel == ref.channel]
            for m in matches:
                if range_satisfies(version_range, str(m.version)):
                    require.ref = m.to_conanfileref()
                    break
            else:
                if self.strict:
                    raise ConanException(f"Requirement '{ref}' not in lockfile")
        else:
            # find exact
            pass

    def update_lock_export_ref(self, ref):
        """ when the recipe is exported, it will complete the missing RREV, otherwise it should
        match the existing RREV
        """
        # Filter existing matching
        ref = RecipeReference.from_conanref(ref)
        if ref not in self.requires:
            # It is inserted in the first position, because that will result in prioritization
            # That includes testing previous versions in a version range
            self.requires.insert(0, ref)
