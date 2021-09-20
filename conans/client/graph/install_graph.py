from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_VIRTUAL, BINARY_SKIP
from conans.model.info import PACKAGE_ID_UNKNOWN


class _InstallGraphNode:
    def __init__(self, node):
        self.pref = node.pref
        self.nodes = [node]  # GraphNode
        self.requires = []  # _InstallGraphNode
        self.binary = node.binary

    def __str__(self):
        return "{}:{}".format(str(self.pref), self.binary)

    def __repr__(self):
        return str(self)


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph):
        self._nodes = []  # _InstallGraphNode
        prefs = {}  # {pref known: _InstallGraphNode}
        deps = {}  # {node: _installGraphNode}

        for node in deps_graph.ordered_iterate():
            if node.recipe in (RECIPE_CONSUMER, RECIPE_VIRTUAL) or node.binary == BINARY_SKIP:
                continue

            if node.pref.id != PACKAGE_ID_UNKNOWN:
                install_node = prefs.get(node.pref)
                if install_node is not None:
                    install_node.nodes.append(node)
                    assert install_node.binary == node.binary
                else:
                    install_node = _InstallGraphNode(node)
                    self._nodes.append(install_node)
                    prefs[node.pref] = install_node
            else:
                install_node = _InstallGraphNode(node)
                self._nodes.append(install_node)

            deps[node] = install_node

            for dep in node.dependencies:
                if dep.dst.binary != BINARY_SKIP:
                    install_node.requires.append(deps[dep.dst])

    def install_order(self):
        # a topological order by levels, returns a list of list, in order of processing
        levels = []
        opened = self._nodes
        while opened:
            current_level = []
            closed = []
            for o in opened:
                requires = o.requires
                if not any(n in opened for n in requires):
                    current_level.append(o)
                    closed.append(o)

            if current_level:
                levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(closed)

        return levels
