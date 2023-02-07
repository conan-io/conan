import json
import os
import textwrap

from conan.api.output import ConanOutput
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    BINARY_MISSING, BINARY_INVALID
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.recipe_ref import RecipeReference
from conans.util.files import load


class _InstallPackageReference:
    """ Represents a single, unique PackageReference to be downloaded, built, etc.
    Same PREF should only be built or downloaded once, but it is possible to have multiple
    nodes in the DepsGraph that share the same PREF.
    PREF could have PREV if to be downloaded (must be the same for all), but won't if to be built
    """
    def __init__(self):
        self.package_id = None
        self.prev = None
        self.nodes = []  # GraphNode
        self.binary = None  # The action BINARY_DOWNLOAD, etc must be the same for all nodes
        self.context = None  # Same PREF could be in both contexts, but only 1 context is enough to
        # be able to reproduce, typically host preferrably
        self.options = []  # to be able to fire a build, the options will be necessary
        self.filenames = []  # The build_order.json filenames e.g. "windows_build_order"
        # If some package, like ICU, requires itself, built for the "build" context architecture
        # to cross compile, there will be a dependency from the current "self" (host context)
        # to that "build" package_id.
        self.depends = []  # List of package_ids of dependencies to other binaries of the same ref

    @staticmethod
    def create(node):
        result = _InstallPackageReference()
        result.package_id = node.pref.package_id
        result.prev = node.pref.revision
        result.binary = node.binary
        result.context = node.context
        # self_options are the minimum to reproduce state
        result.options = node.conanfile.self_options.dumps().splitlines()
        result.nodes.append(node)
        return result

    def add(self, node):
        assert self.package_id == node.package_id
        assert self.binary == node.binary
        assert self.prev == node.prev
        # The context might vary, but if same package_id, all fine
        # assert self.context == node.context
        self.nodes.append(node)

    def serialize(self):
        return {"package_id": self.package_id,
                "prev": self.prev,
                "context": self.context,
                "binary": self.binary,
                "options": self.options,
                "filenames": self.filenames,
                "depends": self.depends}

    @staticmethod
    def deserialize(data, filename):
        result = _InstallPackageReference()
        result.package_id = data["package_id"]
        result.prev = data["prev"]
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        result.filenames = data["filenames"] or [filename]
        result.depends = data["depends"]
        return result


class _InstallRecipeReference:
    """ represents a single, unique Recipe reference (including revision, must have it) containing
    all the _InstallPackageReference that belongs to this RecipeReference. This approach is
    oriented towards a user-intuitive grouping specially in CI, in which all binary variants for the
    same recipe revision (repo+commit) are to be built grouped together"""
    def __init__(self):
        self.ref = None
        self.packages = {}  # {package_id: _InstallPackageReference}
        self.depends = []  # Other REFs, defines the graph topology and operation ordering

    @staticmethod
    def create(node):
        result = _InstallRecipeReference()
        result.ref = node.ref
        result.add(node)
        return result

    def merge(self, other):
        assert self.ref == other.ref
        for d in other.depends:
            if d not in self.depends:
                self.depends.append(d)
        for other_pkgid, other_pkg in other.packages.items():
            existing = self.packages.get(other_pkgid)
            if existing is None:
                self.packages[other_pkgid] = other_pkg
            else:
                assert existing.binary == other_pkg.binary
                for f in other_pkg.filenames:
                    if f not in existing.filenames:
                        existing.filenames.append(f)

    def add(self, node):
        install_pkg_ref = self.packages.get(node.package_id)
        if install_pkg_ref is not None:
            install_pkg_ref.add(node)
        else:
            install_pkg_ref = _InstallPackageReference.create(node)
            self.packages[node.package_id] = install_pkg_ref

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                if dep.dst.ref == node.ref:  # If the node is itself, then it is internal dep
                    install_pkg_ref.depends.append(dep.dst.pref.package_id)
                else:
                    self.depends.append(dep.dst.ref)

    def _install_order(self):
        # TODO: Repeated, refactor
        # a topological order by levels, returns a list of list, in order of processing
        levels = []
        opened = self.packages
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

        return levels

    def serialize(self):
        return {"ref": self.ref.repr_notime(),
                "depends": [ref.repr_notime() for ref in self.depends],
                "packages": [[v.serialize() for v in level] for level in self._install_order()]
                }

    @staticmethod
    def deserialize(data, filename):
        result = _InstallRecipeReference()
        result.ref = RecipeReference.loads(data["ref"])
        for d in data["depends"]:
            result.depends.append(RecipeReference.loads(d))
        for level in data["packages"]:
            for p in level:
                install_node = _InstallPackageReference.deserialize(p, filename)
                result.packages[install_node.package_id] = install_node
        return result


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph=None):
        self._nodes = {}  # ref with rev: _InstallGraphNode

        if deps_graph is not None:
            self._initialize_deps_graph(deps_graph)

    @staticmethod
    def load(filename):
        data = json.loads(load(filename))
        filename = os.path.basename(filename)
        filename = os.path.splitext(filename)[0]
        install_graph = InstallGraph.deserialize(data, filename)
        return install_graph

    def merge(self, other):
        """
        @type other: InstallGraph
        """
        for ref, install_node in other._nodes.items():
            existing = self._nodes.get(ref)
            if existing is None:
                self._nodes[ref] = install_node
            else:
                existing.merge(install_node)

    @staticmethod
    def deserialize(data, filename):
        result = InstallGraph()
        for level in data:
            for item in level:
                elem = _InstallRecipeReference.deserialize(item, filename)
                result._nodes[elem.ref] = elem
        return result

    def _initialize_deps_graph(self, deps_graph):
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary == BINARY_SKIP:
                continue

            existing = self._nodes.get(node.ref)
            if existing is None:
                self._nodes[node.ref] = _InstallRecipeReference.create(node)
            else:
                existing.add(node)

    def install_order(self):
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

        return levels

    def install_build_order(self):
        # TODO: Rename to serialize()?
        """ used for graph build-order and graph build-order-merge commands
        This is basically a serialization of the build-order
        """
        install_order = self.install_order()
        result = [[n.serialize() for n in level] for level in install_order]
        return result

    def raise_errors(self):
        missing, invalid = [], []
        for ref, install_node in self._nodes.items():
            for package in install_node.packages.values():
                if package.binary == BINARY_MISSING:
                    missing.append(package)
                elif package.binary == BINARY_INVALID:
                    invalid.append(package)

        if invalid:
            msg = ["There are invalid packages (packages that cannot exist for this configuration):"]
            for package in invalid:
                node = package.nodes[0]
                if node.cant_build and node.should_build:
                    binary, reason = "Cannot build for this configuration", node.cant_build
                else:
                    binary, reason = "Invalid", node.conanfile.info.invalid
                msg.append("{}: {}: {}".format(node.conanfile, binary, reason))
            raise ConanInvalidConfiguration("\n".join(msg))
        if missing:
            self._raise_missing(missing)

    @staticmethod
    def _raise_missing(missing):
        # TODO: Remove out argument
        # TODO: A bit dirty access to .pref
        missing_prefs = set(n.nodes[0].pref for n in missing)  # avoid duplicated
        missing_prefs_str = list(sorted([str(pref) for pref in missing_prefs]))
        out = ConanOutput()
        for pref_str in missing_prefs_str:
            out.error("Missing binary: %s" % pref_str)
        out.writeln("")

        # Report details just the first one
        install_node = missing[0]
        node = install_node.nodes[0]
        package_id = node.package_id
        ref, conanfile = node.ref, node.conanfile

        msg = f"Can't find a '{ref}' package binary '{package_id}' for the configuration:\n"\
              f"{conanfile.info.dumps()}"
        conanfile.output.warning(msg)
        missing_pkgs = "', '".join(list(sorted([str(pref.ref) for pref in missing_prefs])))
        if len(missing_prefs) >= 5:
            build_str = "--build=missing"
        else:
            build_str = " ".join(list(sorted(["--build=%s" % str(pref.ref) for pref in missing_prefs])))

        raise ConanException(textwrap.dedent('''\
           Missing prebuilt package for '%s'
           Use 'conan list packages %s --format=html -r=remote > table.html' and open the table.html file to see available packages
           Or try to build locally from sources with '%s'

           More Info at 'https://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package'
           ''' % (missing_pkgs, ref, build_str)))
