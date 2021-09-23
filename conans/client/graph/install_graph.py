import textwrap

from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP, \
    BINARY_MISSING, BINARY_INVALID, BINARY_ERROR
from conans.errors import ConanInvalidConfiguration, ConanException
from conans.model.info import PACKAGE_ID_UNKNOWN


class _InstallGraphPackage:
    def __init__(self, node):
        self.pref = node.pref
        self.package_id = node.pref.id
        self.prev = node.pref.revision
        self.nodes = [node]  # GraphNode
        self.binary = node.binary
        self.context = node.context

    def add(self, node):
        assert self.package_id == node.pref.id
        assert self.binary == node.binary
        assert self.context == node.context
        assert self.prev == node.prev
        self.nodes.append(node)

    def serialize(self):
        node = self.nodes[0]
        # FIXME: The aggregation of the upstream is not correct here
        options = node.conanfile.options.values.as_list()
        return {"package_id": self.package_id,
                "context": self.context,
                "binary": self.binary,
                "prev": self.prev,
                "options": options,
                }


class _InstallGraphNode:
    def __init__(self, node):
        self.ref = node.ref
        self.packages = []
        self._package_ids = {}
        self.depends = []  # Other refs
        self.add(node)

    def add(self, node):
        pkg = _InstallGraphPackage(node)
        if node.pref.id == PACKAGE_ID_UNKNOWN:
            self.packages.append(pkg)
        else:
            existing = self._package_ids.get(node.pref.id)
            if existing is not None:
                existing.add(node)
            else:
                self.packages.append(pkg)

        for dep in node.dependencies:
            if dep.dst.binary != BINARY_SKIP:
                self.depends.append(dep.dst.ref)

    def serialize(self):
        return {"ref": repr(self.ref),
                "depends": [repr(ref) for ref in self.depends],
                "packages": [p.serialize() for p in self.packages],
                }


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph=None):
        self._nodes = {}  # ref with rev: _InstallGraphNode

        if deps_graph is not None:
            self._initialize_deps_graph(deps_graph)

    def _initialize_deps_graph(self, deps_graph):
        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary == BINARY_SKIP:
                continue

            existing = self._nodes.get(node.ref)
            if existing is None:
                self._nodes[node.ref] = _InstallGraphNode(node)
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
    conanfile.output.warn(msg)
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
