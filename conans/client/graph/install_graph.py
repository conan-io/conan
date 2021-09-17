from collections import OrderedDict


class _InstallGraphNode:
    def __init__(self, pref):
        self.pref = pref
        self.nodes = []  # GraphNode
        self.requires = []  # prefs
        self.binary = None

    def __str__(self):
        return "{}:{}".format(str(self.pref), self.binary)


class InstallGraph:
    """ A graph containing the package references in order to be built/downloaded
    """

    def __init__(self, deps_graph):
        self._nodes = OrderedDict()  # {pref: _InstallGraphNode}

        for node in deps_graph.nodes:
            n = self._nodes.setdefault(node.pref, _InstallGraphNode(node.pref))
            n.nodes.append(node)
            if n.binary is None:
                n.binary = node.binary
            else:  # all nodes with the same pref should have the same binary action
                assert n.binary == node.binary

            for dep in node.dependencies:
                n.requires.append(dep.dst.pref)

    def install_order(self):
        # First do a topological order by levels, the prefs of the nodes are stored
        levels = []
        opened = list(self._nodes.keys())
        while opened:
            current_level = []
            closed = []
            for o in opened:
                node = self._nodes[o]
                requires = node.requires
                if not any(n in opened for n in requires):  # Doesn't have an open requires
                    current_level.append(node)
                    closed.append(o)

            if current_level:
                levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(closed)

        return levels
