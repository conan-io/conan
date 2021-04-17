from collections import OrderedDict


class InstallGraph:
    """
    """

    def __init__(self, deps_graph):
        self._nodes = OrderedDict()

        for node in deps_graph.nodes:
            n = self._nodes.setdefault(node.pref, {})
            n.setdefault("nodes", []).append(node)

            for dep in node.dependencies:
                n.setdefault("requires", []).append(dep.dst.pref)

    def items(self):
        return self._nodes.items()

    def install_order(self):
        # First do a topological order by levels, the ids of the nodes are stored
        levels = []
        opened = list(self._nodes.keys())
        while opened:
            current_level = []
            closed = []
            for o in opened:
                node = self._nodes[o]
                requires = node.get("requires", [])
                if not any(n in opened for n in requires):  # Doesn't have an open requires
                    # iterate all packages to see if some has prev=null
                    current_level.append(o)
                    closed.append(o)

            if current_level:
                levels.append(current_level)
            # now initialize new level
            opened = set(opened).difference(closed)

        return levels
