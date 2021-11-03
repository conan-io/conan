import json
import os
import textwrap

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    BINARY_MISSING, BINARY_INVALID, BINARY_ERROR
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.ref import ConanFileReference
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
                "filenames": self.filenames}

    @staticmethod
    def deserialize(data, filename):
        result = _InstallPackageReference()
        result.package_id = data["package_id"]
        result.prev = data["prev"]
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        result.filenames = data["filenames"] or [filename]
        return result


class _InstallRecipeReference:
    """ represents a single, unique Recipe reference (including revision, must have it) containing
    all the _InstallPackageReference that belongs to this RecipeReference. This approach is
    oriented towards a user-intuitive grouping specially in CI, in which all binary variants for the
    same recipe revision (repo+commit) are to be built grouped together"""
    def __init__(self):
        self.ref = None
        self.packages = []  # _InstallPackageReference
        self.depends = []  # Other REFs, defines the graph topology and operation ordering
        # implementation detail
        self._package_ids = {}  # caching {package_id: _InstallPackageReference}

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
        for p in other.packages:
            existing = self._package_ids.get(p.package_id)
            if existing is None:
                self.packages.append(p)
            else:
                assert existing.binary == p.binary
                for f in p.filenames:
                    if f not in existing.filenames:
                        existing.filenames.append(f)

    def update_unknown(self, package):
        package_id = package.package_id
        if package_id == PACKAGE_ID_UNKNOWN:
            return False
        existing = self._package_ids.get(package_id)
        if existing:
            return False
        self._package_ids[package_id] = package
        return True

    def add(self, node):
        if node.package_id == PACKAGE_ID_UNKNOWN:
            # PACKAGE_ID_UNKNOWN are all different items, because when package_id is computed
            # it could be different
            self.packages.append(_InstallPackageReference.create(node))
        else:
            existing = self._package_ids.get(node.package_id)
            if existing is not None:
                existing.add(node)
            else:
                pkg = _InstallPackageReference.create(node)
                self.packages.append(pkg)
                self._package_ids[node.package_id] = pkg

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                self.depends.append(dep.dst.ref)

    def serialize(self):
        return {"ref": repr(self.ref),
                "depends": [repr(ref) for ref in self.depends],
                "packages": [p.serialize() for p in self.packages],
                }

    @staticmethod
    def deserialize(data, filename):
        result = _InstallRecipeReference()
        result.ref = ConanFileReference.loads(data["ref"])
        for d in data["depends"]:
            result.depends.append(ConanFileReference.loads(d))
        for p in data["packages"]:
            install_node = _InstallPackageReference.deserialize(p, filename)
            result.packages.append(install_node)
            result._package_ids[install_node.package_id] = install_node
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
        install_order = self.install_order()
        result = []
        for level in install_order:
            simple_level = []
            for node in level:
                simple_level.append(node.serialize())
            if simple_level:
                result.append(simple_level)
        return result

    def raise_errors(self, out):
        missing, invalid = [], []
        for ref, install_node in self._nodes.items():
            for package in install_node.packages:
                if package.binary == BINARY_MISSING:
                    missing.append(package)
                elif package.binary in (BINARY_INVALID, BINARY_ERROR):
                    invalid.append(package)

        if invalid:
            msg = ["There are invalid packages (packages that cannot exist for this configuration):"]
            for package in invalid:
                node = package.nodes[0]
                binary, reason = node.conanfile.info.invalid
                msg.append("{}: {}: {}".format(node.conanfile, binary, reason))
            raise ConanInvalidConfiguration("\n".join(msg))
        if missing:
            raise_missing(missing, out)


def raise_missing(missing, out):
    # TODO: Remove out argument
    # TODO: A bit dirty access to .pref
    missing_prefs = set(n.nodes[0].pref for n in missing)  # avoid duplicated
    missing_prefs_str = list(sorted([str(pref) for pref in missing_prefs]))
    for pref_str in missing_prefs_str:
        out.error("Missing binary: %s" % pref_str)
    out.writeln("")

    # Report details just the first one
    install_node = missing[0]
    node = install_node.nodes[0]
    package_id = node.package_id
    ref, conanfile = node.ref, node.conanfile
    dependencies = [str(dep.dst) for dep in node.dependencies]

    settings_text = ", ".join(conanfile.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conanfile.info.options.dumps().splitlines())
    dependencies_text = ', '.join(dependencies)
    requires_text = ", ".join(conanfile.info.requires.dumps().splitlines())

    msg = textwrap.dedent('''\
       Can't find a '%s' package for the specified settings, options and dependencies:
       - Settings: %s
       - Options: %s
       - Dependencies: %s
       - Requirements: %s
       - Package ID: %s
       ''' % (ref, settings_text, options_text, dependencies_text, requires_text, package_id))
    conanfile.output.warning(msg)
    missing_pkgs = "', '".join(list(sorted([str(pref.ref) for pref in missing_prefs])))
    if len(missing_prefs) >= 5:
        build_str = "--build=missing"
    else:
        build_str = " ".join(list(sorted(["--build=%s" % pref.ref.name for pref in missing_prefs])))

    raise ConanException(textwrap.dedent('''\
       Missing prebuilt package for '%s'
       Try to build from sources with '%s'
       Use 'conan search <reference> --table table.html'
       Or read 'http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package'
       ''' % (missing_pkgs, build_str)))
