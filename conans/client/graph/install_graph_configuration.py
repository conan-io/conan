import json
import os

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    Overrides, BINARY_BUILD
from conans.model.package_ref import PkgReference
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load


class _InstallPackageReference:
    """ Represents a single, unique PackageReference to be downloaded, built, etc.
    Same PREF should only be built or downloaded once, but it is possible to have multiple
    nodes in the DepsGraph that share the same PREF.
    PREF could have PREV if to be downloaded (must be the same for all), but won't if to be built
    """
    def __init__(self):
        self.ref = None
        self.package_id = None
        self.prev = None
        self.nodes = []  # GraphNode
        self.binary = None  # The action BINARY_DOWNLOAD, etc must be the same for all nodes
        self.context = None  # Same PREF could be in both contexts, but only 1 context is enough to
        # be able to reproduce, typically host preferrably
        self.options = []  # to be able to fire a build, the options will be necessary
        self.filenames = []  # The build_order.json filenames e.g. "windows_build_order"
        self.depends = []  # List of full prefs
        self.overrides = Overrides()

    @property
    def pref(self):
        return PkgReference(self.ref, self.package_id, self.prev)

    @property
    def conanfile(self):
        return self.nodes[0].conanfile

    @staticmethod
    def create(node):
        result = _InstallPackageReference()
        result.ref = node.ref
        result.package_id = node.pref.package_id
        result.prev = node.pref.revision
        result.binary = node.binary
        result.context = node.context
        # self_options are the minimum to reproduce state
        result.options = node.conanfile.self_options.dumps().splitlines()
        result.overrides = node.overrides()

        result.nodes.append(node)
        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                if dep.dst.pref not in result.depends:
                    result.depends.append(dep.dst.pref)
        return result

    def add(self, node):
        assert self.package_id == node.package_id, f"{self.pref}!={node.pref}"
        assert self.binary == node.binary, f"Binary for {node}: {self.binary}!={node.binary}"
        assert self.prev == node.prev
        # The context might vary, but if same package_id, all fine
        # assert self.context == node.context
        self.nodes.append(node)

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                if dep.dst.pref not in self.depends:
                    self.depends.append(dep.dst.pref)

    def _build_args(self):
        if self.binary != BINARY_BUILD:
            return None
        cmd = f"--require={self.ref}" if self.context == "host" else f"--tool-require={self.ref}"
        cmd += f" --build={self.ref}"
        if self.options:
            cmd += " " + " ".join(f"-o {o}" for o in self.options)
        if self.overrides:
            cmd += f' --lockfile-overrides="{self.overrides}"'
        return cmd

    def serialize(self):
        return {"ref": self.ref.repr_notime(),
                "pref": self.pref.repr_notime(),
                "package_id": self.pref.package_id,
                "prev": self.pref.revision,
                "context": self.context,
                "binary": self.binary,
                "options": self.options,
                "filenames": self.filenames,
                "depends": [d.repr_notime() for d in self.depends],
                "overrides": self.overrides.serialize(),
                "build_args": self._build_args()
                }

    @staticmethod
    def deserialize(data, filename):
        result = _InstallPackageReference()
        result.ref = RecipeReference.loads(data["ref"])
        result.package_id = data["package_id"]
        result.prev = data["prev"]
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        result.filenames = data["filenames"] or [filename]
        result.depends = [PkgReference.loads(p) for p in data["depends"]]
        result.overrides = Overrides.deserialize(data["overrides"])
        return result

    def merge(self, other):
        assert self.ref == other.ref
        for d in other.depends:
            if d not in self.depends:
                self.depends.append(d)

        for d in other.filenames:
            if d not in self.filenames:
                self.filenames.append(d)


class InstallGraphConfiguration:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph=None):
        self._nodes = {}  # {pref: _InstallGraphPackage}

        self._is_test_package = False
        if deps_graph is not None:
            self._initialize_deps_graph(deps_graph)
            self._is_test_package = deps_graph.root.conanfile.tested_reference_str is not None

    @staticmethod
    def load(filename):
        data = json.loads(load(filename))
        filename = os.path.basename(filename)
        filename = os.path.splitext(filename)[0]
        install_graph = InstallGraphConfiguration.deserialize(data, filename)
        return install_graph

    def merge(self, other):
        """
        @type other: InstallGraphConfiguration
        """
        for ref, install_node in other._nodes.items():
            existing = self._nodes.get(ref)
            if existing is None:
                self._nodes[ref] = install_node
            else:
                existing.merge(install_node)

    @staticmethod
    def deserialize(data, filename):
        result = InstallGraphConfiguration()
        for level in data:
            for item in level:
                elem = _InstallPackageReference.deserialize(item, filename)
                result._nodes[elem.pref] = elem
        return result

    def _initialize_deps_graph(self, deps_graph):
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary == BINARY_SKIP:
                continue

            existing = self._nodes.get(node.pref)
            if existing is None:
                self._nodes[node.pref] = _InstallPackageReference.create(node)
            else:
                existing.add(node)

    def install_order(self, flat=False):
        # a topological order by levels, returns a list of list, in order of processing
        levels = []
        opened = self._nodes
        while opened:
            current_level = []
            closed = []
            for o in opened.values():
                requires = o.depends
                if not any(n in opened for n in requires):
                    current_level.append(o)
                    closed.append(o)

            if current_level:
                levels.append(current_level)
            # now initialize new level
            opened = {k: v for k, v in opened.items() if v not in closed}
        if flat:
            return [r for level in levels for r in level]
        return levels

    def install_build_order(self):
        # TODO: Rename to serialize()?
        """ used for graph build-order and graph build-order-merge commands
        This is basically a serialization of the build-order
        """
        install_order = self.install_order()
        result = [[n.serialize() for n in level] for level in install_order]
        return result
