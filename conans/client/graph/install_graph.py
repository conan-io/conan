import textwrap

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    BINARY_MISSING, BINARY_INVALID, BINARY_ERROR
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN
from conans.model.ref import PackageReference, ConanFileReference


class _InstallGraphPackage:
    def __init__(self):
        self.pref = None
        self.nodes = []  # GraphNode
        self.binary = None
        self.context = None
        self.options = []

    @staticmethod
    def create(node):
        result = _InstallGraphPackage()
        result.pref = node.pref
        result.binary = node.binary
        result.context = node.context
        # FIXME: The aggregation of the upstream options is not correct here
        result.options = node.conanfile.options.values.as_list()
        result.nodes.append(node)
        return result

    def add(self, node):
        assert self.pref == node.pref
        assert self.binary == node.binary
        # The context might vary, but if same package_id, all fine
        # assert self.context == node.context
        self.nodes.append(node)

    def serialize(self):
        return {"pref": repr(self.pref),
                "context": self.context,
                "binary": self.binary,
                "options": self.options}

    @staticmethod
    def deserialize(data):
        result = _InstallGraphPackage()
        result.pref = PackageReference.loads(data["pref"])
        result.binary = data["binary"]
        result.context = data["context"]
        result.options = data["options"]
        return result


class _InstallGraphNode:
    def __init__(self):
        self.ref = None
        self.packages = []
        self._package_ids = {}
        self.depends = []  # Other refs

    @staticmethod
    def create(node):
        result = _InstallGraphNode()
        result.ref = node.ref
        result.add(node)
        return result

    def merge(self, other):
        assert self.ref == other.ref


    def add(self, node):
        if node.pref.id == PACKAGE_ID_UNKNOWN:
            self.packages.append(_InstallGraphPackage.create(node))
        else:
            existing = self._package_ids.get(node.pref.id)
            if existing is not None:
                existing.add(node)
            else:
                pkg = _InstallGraphPackage.create(node)
                self.packages.append(pkg)
                self._package_ids[node.pref.id] = pkg

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                self.depends.append(dep.dst.ref)

    def serialize(self):
        return {"ref": repr(self.ref),
                "depends": [repr(ref) for ref in self.depends],
                "packages": [p.serialize() for p in self.packages],
                }

    @staticmethod
    def deserialize(data):
        result = _InstallGraphNode()
        result.ref = ConanFileReference.loads(data["ref"])
        for d in data["depends"]:
            result.depends.append(ConanFileReference.loads(d))
        for p in data["packages"]:
            result.packages.append(_InstallGraphPackage.deserialize(p))
        return result


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph=None):
        self._nodes = {}  # ref with rev: _InstallGraphNode

        if deps_graph is not None:
            self._initialize_deps_graph(deps_graph)

    def merge(self, other):
        for ref, install_node in other._nodes.items():
            existing = self._nodes.get(ref)
            if existing is None:
                self._nodes[ref] = install_node
            else:
                existing.merge(install_node)

    @staticmethod
    def deserialize(data):
        result = InstallGraph()
        for level in data:
            for item in level:
                elem = _InstallGraphNode.deserialize(item)
                result._nodes[elem.ref] = elem
        return result

    def _initialize_deps_graph(self, deps_graph):
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary == BINARY_SKIP:
                continue

            existing = self._nodes.get(node.ref)
            if existing is None:
                self._nodes[node.ref] = _InstallGraphNode.create(node)
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
    missing_prefs = list(sorted(missing_prefs))
    for pref in missing_prefs:
        out.error("Missing binary: %s" % str(pref))
    out.writeln("")

    # Report details just the first one
    install_node = missing[0]
    node = install_node.nodes[0]
    package_id = node.package_id
    ref, conanfile = node.ref, node.conanfile
    dependencies = [str(dep.dst) for dep in node.dependencies]

    settings_text = ", ".join(conanfile.info.full_settings.dumps().splitlines())
    options_text = ", ".join(conanfile.info.full_options.dumps().splitlines())
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
    missing_pkgs = "', '".join([str(pref.ref) for pref in missing_prefs])
    if len(missing_prefs) >= 5:
        build_str = "--build=missing"
    else:
        build_str = " ".join(["--build=%s" % pref.ref.name for pref in missing_prefs])

    raise ConanException(textwrap.dedent('''\
       Missing prebuilt package for '%s'
       Try to build from sources with '%s'
       Use 'conan search <reference> --table table.html'
       Or read 'http://docs.conan.io/en/latest/faq/troubleshooting.html#error-missing-prebuilt-package'
       ''' % (missing_pkgs, build_str)))
