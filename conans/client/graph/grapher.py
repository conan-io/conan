from conans.client.graph.graph import BINARY_BUILD, BINARY_CACHE, BINARY_DOWNLOAD, BINARY_MISSING, \
    BINARY_UPDATE
from conans.client.installer import build_id


class Node(object):
    def __init__(self, id, node, is_build_time_node):
        self.id = id
        self._ref = node.ref
        self._conanfile = node.conanfile
        self._is_build_time_node = is_build_time_node
        self.package_id = node.package_id
        self.binary = node.binary

    @property
    def label(self):
        return self._conanfile.display_name

    @property
    def short_label(self):
        if self._ref and self._ref.name:
            return "{}/{}".format(self._ref.name, self._ref.version)
        else:
            return self.label

    @property
    def is_build_requires(self):
        return self._is_build_time_node

    def data(self):

        def ensure_iterable(value):
            if isinstance(value, (list, tuple)):
                return value
            return value,

        return {
            'build_id': build_id(self._conanfile),
            'url': self._conanfile.url,
            'homepage': self._conanfile.homepage,
            'license': self._conanfile.license,
            'author': self._conanfile.author,
            'topics': ensure_iterable(self._conanfile.topics) if self._conanfile.topics else None
        }


class Grapher(object):
    def __init__(self, deps_graph):
        self._deps_graph = deps_graph
        self.nodes, self.edges = self._build_graph()

    def _build_graph(self):
        graph_nodes = self._deps_graph.by_levels()
        build_time_nodes = self._deps_graph.build_time_nodes()
        graph_nodes = reversed([n for level in graph_nodes for n in level])

        _node_map = {}
        for i, node in enumerate(graph_nodes):
            n = Node(i, node, bool(node in build_time_nodes))
            _node_map[node] = n

        edges = []
        for node in self._deps_graph.nodes:
            for node_to in node.neighbors():
                src = _node_map[node]
                dst = _node_map[node_to]
                edges.append((src, dst))

        return _node_map.values(), edges

    def binary_color(self, node):
        assert isinstance(node, Node), "Wrong type '{}'".format(type(node))
        color = {BINARY_CACHE: "SkyBlue",
                 BINARY_DOWNLOAD: "LightGreen",
                 BINARY_BUILD: "Khaki",
                 BINARY_MISSING: "OrangeRed",
                 BINARY_UPDATE: "SeaGreen"}.get(node.binary, "White")
        return color
