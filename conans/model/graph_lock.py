from conans.model.ref import PackageReference
from conans.errors import ConanException
from conans.client.graph.graph import RECIPE_VIRTUAL, RECIPE_CONSUMER


class GraphLock(object):

    def __init__(self, graph=None):
        self._nodes = {}  # {numeric id: PREF or None}
        self._edges = {}  # {numeric_id: [numeric_ids]}
        if graph:
            for node in graph.nodes:
                dependencies = []
                for edge in node.dependencies:
                    dependencies.append(edge.dst.id)
                # The pref.ref CAN BE None, for conanfile.txt
                self._nodes[node.id] = (node.pref if node.recipe not in (RECIPE_VIRTUAL,
                                                                         RECIPE_CONSUMER)
                                        else None)
                self._edges[node.id] = dependencies

    def pref(self, node_id):
        return self._nodes[node_id]

    def dependencies(self, node_id):
        # return {pkg_name: PREF}
        return {self._nodes[i].ref.name: (self._nodes[i], i) for i in self._edges[node_id]}

    def get_node(self, ref):
        # Build a map to search by REF without REV
        inverse_map = {}
        for id_, pref in self._nodes.items():
            inverse_map.setdefault(pref.ref.copy_clear_rev() if pref else None,
                                   {})[pref.id if pref else None] = id_

        try:
            binaries = inverse_map[ref.copy_clear_rev() if ref else None]
        except KeyError:
            binaries = inverse_map[None]

        if len(binaries) == 1:
            id_ = next(iter(binaries.values()))
            assert id_
            return id_
        else:
            raise ConanException("There are %s binaries for ref %s" % (len(binaries), ref))

    def update_ref(self, ref):
        node_id = self.get_node(ref)
        self._nodes[node_id] = PackageReference(ref, "Unkonwn Package ID")

    def find_node(self, node, reference):
        if node.recipe == RECIPE_VIRTUAL:
            assert reference
            node_id = self.get_node(reference)
            self._nodes[node.id] = None
            self._edges[node.id] = [node_id]
            return

        assert node.recipe == RECIPE_CONSUMER
        node_id = self.get_node(None)
        node.id = node_id

    @staticmethod
    def from_dict(data):
        if data is None:
            return None

        graph_lock = GraphLock()
        for id_, pref in data["nodes"].items():
            graph_lock._nodes[id_] = PackageReference.loads(pref) if pref else None
        for id_, dependencies in data["edges"].items():
            graph_lock._edges[id_] = dependencies
        return graph_lock

    def as_dict(self):
        result = {}
        nodes = {}
        for id_, pref in self._nodes.items():
            nodes[id_] = pref.full_repr() if pref else None
        result["nodes"] = nodes
        result["edges"] = self._edges
        return result
