import json
import os
import textwrap

from conan.api.output import ConanOutput
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    BINARY_MISSING, BINARY_INVALID, Overrides, BINARY_BUILD, BINARY_EDITABLE_BUILD, BINARY_PLATFORM
from conans.errors import ConanInvalidConfiguration, ConanException
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
        self.overrides = Overrides()
        self.ref = None

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
        result.nodes.append(node)
        result.overrides = node.overrides()
        return result

    def add(self, node):
        assert self.package_id == node.package_id
        assert self.binary == node.binary, f"Binary for {node}: {self.binary}!={node.binary}"
        assert self.prev == node.prev
        # The context might vary, but if same package_id, all fine
        # assert self.context == node.context
        self.nodes.append(node)

    def _build_args(self):
        if self.binary != BINARY_BUILD:
            return None
        cmd = f"--requires={self.ref}" if self.context == "host" else f"--tool-requires={self.ref}"
        cmd += f" --build={self.ref}"
        if self.options:
            cmd += " " + " ".join(f"-o {o}" for o in self.options)
        if self.overrides:
            cmd += f' --lockfile-overrides="{self.overrides}"'
        return cmd

    def serialize(self):
        return {"package_id": self.package_id,
                "prev": self.prev,
                "context": self.context,
                "binary": self.binary,
                "options": self.options,
                "filenames": self.filenames,
                "depends": self.depends,
                "overrides": self.overrides.serialize(),
                "build_args": self._build_args()}

    @staticmethod
    def deserialize(data, filename, ref):
        result = _InstallPackageReference()
        result.ref = ref
        result.package_id = data["package_id"]
        result.prev = data["prev"]
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        result.filenames = data["filenames"] or [filename]
        result.depends = data["depends"]
        result.overrides = Overrides.deserialize(data["overrides"])
        return result


class _InstallRecipeReference:
    """ represents a single, unique Recipe reference (including revision, must have it) containing
    all the _InstallPackageReference that belongs to this RecipeReference. This approach is
    oriented towards a user-intuitive grouping specially in CI, in which all binary variants for the
    same recipe revision (repo+commit) are to be built grouped together"""
    def __init__(self):
        self.ref = None
        self._node = None
        self.packages = {}  # {package_id: _InstallPackageReference}
        self.depends = []  # Other REFs, defines the graph topology and operation ordering

    def __str__(self):
        return f"{self.ref} ({self._node.binary}) -> {[str(d) for d in self.depends]}"

    @property
    def need_build(self):
        for package in self.packages.values():
            if package.binary in (BINARY_BUILD, BINARY_EDITABLE_BUILD):
                return True
        return False

    @property
    def node(self):
        return self._node

    @staticmethod
    def create(node):
        result = _InstallRecipeReference()
        result._node = node
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
                elif dep.dst.ref not in self.depends:
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
                install_node = _InstallPackageReference.deserialize(p, filename, result.ref)
                result.packages[install_node.package_id] = install_node
        return result


class _InstallConfiguration:
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

    def __str__(self):
        return f"{self.ref}:{self.package_id} ({self.binary}) -> {[str(d) for d in self.depends]}"

    @property
    def need_build(self):
        return self.binary in (BINARY_BUILD, BINARY_EDITABLE_BUILD)

    @property
    def pref(self):
        return PkgReference(self.ref, self.package_id, self.prev)

    @property
    def conanfile(self):
        return self.nodes[0].conanfile

    @staticmethod
    def create(node):
        result = _InstallConfiguration()
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
        cmd = f"--requires={self.ref}" if self.context == "host" else f"--tool-requires={self.ref}"
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
        result = _InstallConfiguration()
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
        assert self.binary == other.binary, f"Binary for {self.ref}: {self.binary}!={other.binary}"

        assert self.ref == other.ref
        for d in other.depends:
            if d not in self.depends:
                self.depends.append(d)

        for d in other.filenames:
            if d not in self.filenames:
                self.filenames.append(d)


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph, order_by=None):
        self._nodes = {}  # ref with rev: _InstallGraphNode
        order_by = order_by or "recipe"
        self._order = order_by
        self._node_cls = _InstallRecipeReference if order_by == "recipe" else _InstallConfiguration
        self._is_test_package = False
        self.reduced = False
        if deps_graph is not None:
            self._initialize_deps_graph(deps_graph)
            self._is_test_package = deps_graph.root.conanfile.tested_reference_str is not None

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
        if self.reduced or other.reduced:
            raise ConanException("Reduced build-order files cannot be merged")
        if self._order != other._order:
            raise ConanException(f"Cannot merge build-orders of {self._order}!={other._order}")
        for ref, install_node in other._nodes.items():
            existing = self._nodes.get(ref)
            if existing is None:
                self._nodes[ref] = install_node
            else:
                existing.merge(install_node)

    @staticmethod
    def deserialize(data, filename):
        legacy = isinstance(data, list)
        order, data, reduced = ("recipe", data, False) if legacy else \
            (data["order_by"], data["order"], data["reduced"])
        result = InstallGraph(None, order_by=order)
        result.reduced = reduced
        result.legacy = legacy
        for level in data:
            for item in level:
                elem = result._node_cls.deserialize(item, filename)
                key = elem.ref if order == "recipe" else elem.pref
                result._nodes[key] = elem
        return result

    def _initialize_deps_graph(self, deps_graph):
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) \
                    or node.binary in (BINARY_SKIP, BINARY_PLATFORM):
                continue

            key = node.ref if self._order == "recipe" else node.pref
            existing = self._nodes.get(key)
            if existing is None:
                self._nodes[key] = self._node_cls.create(node)
            else:
                existing.add(node)

    def reduce(self):
        result = {}
        for k, node in self._nodes.items():
            if node.need_build:
                result[k] = node
            else:  # Eliminate this element from the graph
                dependencies = node.depends
                # Find all consumers
                for n in self._nodes.values():
                    if k in n.depends:
                        n.depends = [d for d in n.depends if d != k]  # Discard the removed node
                        # Add new edges, without repetition
                        n.depends.extend(d for d in dependencies if d not in n.depends)
        self._nodes = result
        self.reduced = True

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
            else:
                self._raise_loop_detected(opened)

            # now initialize new level
            opened = {k: v for k, v in opened.items() if v not in closed}
        if flat:
            return [r for level in levels for r in level]
        return levels

    @staticmethod
    def _raise_loop_detected(nodes):
        """
        We can exclude the nodes that have already been processed they do not content loops
        """
        msg = [f"{n}" for n in nodes.values()]
        msg = "\n".join(msg)
        instructions = "This graph is ill-formed, and cannot be installed\n" \
                       "Most common cause is having dependencies both in build and host contexts\n"\
                       "forming a cycle, due to tool_requires having transitive requires.\n"\
                       "Check your profile [tool_requires] and recipe tool and regular requires\n"\
                       "You might inspect the dependency graph with:\n"\
                       "  $ conan graph info . --format=html > graph.html"
        raise ConanException("There is a loop in the graph (some packages already ommitted):\n"
                             f"{msg}\n\n{instructions}")

    def install_build_order(self):
        # TODO: Rename to serialize()?
        """ used for graph build-order and graph build-order-merge commands
        This is basically a serialization of the build-order
        """
        install_order = self.install_order()
        result = {"order_by": self._order,
                  "reduced": self.reduced,
                  "order": [[n.serialize() for n in level] for level in install_order]}
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
            msg = ["There are invalid packages:"]
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

    def _raise_missing(self, missing):
        # TODO: Remove out argument
        # TODO: A bit dirty access to .pref
        missing_prefs = set(n.nodes[0].pref for n in missing)  # avoid duplicated
        missing_prefs_str = list(sorted([str(pref) for pref in missing_prefs]))
        out = ConanOutput()
        for pref_str in missing_prefs_str:
            out.error(f"Missing binary: {pref_str}", error_type="exception")
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
        if self._is_test_package:
            build_msg = "This is a **test_package** missing binary. You can use --build (for " \
                        "all dependencies) or --build-test (exclusive for 'test_package' " \
                        "dependencies) to define what can be built from sources"
        else:
            if len(missing_prefs) >= 5:
                build_str = "--build=missing"
            else:
                build_str = " ".join(list(sorted(["--build=%s" % str(pref.ref)
                                                  for pref in missing_prefs])))
            build_msg = f"Try to build locally from sources using the '{build_str}' argument"

        raise ConanException(textwrap.dedent(f'''\
           Missing prebuilt package for '{missing_pkgs}'. You can try:
               - List all available packages using 'conan list "{ref}:*" -r=remote'
               - Explain missing binaries: replace 'conan install ...' with 'conan graph explain ...'
               - {build_msg}

           More Info at 'https://docs.conan.io/2/knowledge/faq.html#error-missing-prebuilt-package'
           '''))
