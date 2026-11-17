from unittest.mock import Mock

from conan.internal.graph.graph import CONTEXT_HOST
from conan.internal.graph.graph_builder import DepsGraph, Node
from conan.internal.model.conan_file import ConanFile
from conan.api.model import RecipeReference


class TestDepsGraph:

    def test_node(self):
        """ nodes are different even if contain same values,
        so they can be repeated if necessary in the graph (common
        static libraries)
        """
        ref1 = RecipeReference.loads("hello/0.1@user/stable")
        ref2 = RecipeReference.loads("hello/0.1@user/stable")

        conanfile1 = ConanFile(None)
        conanfile2 = ConanFile(None)
        n1 = Node(ref1, conanfile1, context=CONTEXT_HOST)
        n2 = Node(ref2, conanfile2, context=CONTEXT_HOST)

        assert n1 != n2

    def test_basic_levels(self):
        ref1 = RecipeReference.loads("hello/1.0@user/stable")
        ref2 = RecipeReference.loads("hello/2.0@user/stable")
        ref3 = RecipeReference.loads("hello/3.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, Mock(), context=CONTEXT_HOST)
        n2 = Node(ref2, Mock(), context=CONTEXT_HOST)
        n3 = Node(ref3, Mock(), context=CONTEXT_HOST)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n3)
        deps.add_edge(n1, n2, None)
        deps.add_edge(n2, n3, None)
        assert [[n3], [n2], [n1]] == deps.by_levels()

    def test_multi_levels(self):
        ref1 = RecipeReference.loads("hello/1.0@user/stable")
        ref2 = RecipeReference.loads("hello/2.0@user/stable")
        ref31 = RecipeReference.loads("hello/31.0@user/stable")
        ref32 = RecipeReference.loads("hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, Mock(), context=CONTEXT_HOST)
        n2 = Node(ref2, Mock(), context=CONTEXT_HOST)
        n31 = Node(ref31, Mock(), context=CONTEXT_HOST)
        n32 = Node(ref32, Mock(), context=CONTEXT_HOST)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2, None)
        deps.add_edge(n2, n31, None)
        deps.add_edge(n2, n32, None)
        assert [[n31, n32], [n2], [n1]] == deps.by_levels()

    def test_multi_levels_2(self):

        ref1 = RecipeReference.loads("hello/1.0@user/stable")
        ref2 = RecipeReference.loads("hello/2.0@user/stable")
        ref5 = RecipeReference.loads("hello/5.0@user/stable")
        ref31 = RecipeReference.loads("hello/31.0@user/stable")
        ref32 = RecipeReference.loads("hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, Mock(), context=CONTEXT_HOST)
        n2 = Node(ref2, Mock(), context=CONTEXT_HOST)
        n5 = Node(ref5, Mock(), context=CONTEXT_HOST)
        n31 = Node(ref31, Mock(), context=CONTEXT_HOST)
        n32 = Node(ref32, Mock(), context=CONTEXT_HOST)
        deps.add_node(n1)
        deps.add_node(n5)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2, None)
        deps.add_edge(n1, n5, None)
        deps.add_edge(n2, n31, None)
        deps.add_edge(n2, n32, None)
        assert [[n31, n32, n5], [n2], [n1]] == deps.by_levels()

    def test_multi_levels_3(self):

        ref1 = RecipeReference.loads("hello/1.0@user/stable")
        ref2 = RecipeReference.loads("hello/2.0@user/stable")
        ref5 = RecipeReference.loads("hello/5.0@user/stable")
        ref31 = RecipeReference.loads("hello/31.0@user/stable")
        ref32 = RecipeReference.loads("hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, Mock(), context=CONTEXT_HOST)
        n2 = Node(ref2, Mock(), context=CONTEXT_HOST)
        n5 = Node(ref5, Mock(), context=CONTEXT_HOST)
        n31 = Node(ref31, Mock(), context=CONTEXT_HOST)
        n32 = Node(ref32, Mock(), context=CONTEXT_HOST)
        deps.add_node(n1)
        deps.add_node(n5)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2, None)
        deps.add_edge(n1, n5, None)
        deps.add_edge(n2, n31, None)
        deps.add_edge(n2, n32, None)
        deps.add_edge(n32, n5, None)
        assert [[n31, n5], [n32], [n2], [n1]] == deps.by_levels()


class TestSubgraph:

    def test_subgraph_order(self):
        # diamond: a -> (b, c) -> d
        a, b, c, d = self._nodes("a", "b", "c", "d")
        self._link(a, b)
        self._link(a, c)
        self._link(b, d)
        self._link(c, d)
        assert d.subgraph().nodes == [d]
        assert b.subgraph().nodes == [b, d]
        assert c.subgraph().nodes == [c, d]
        assert a.subgraph().nodes == [a, b, c, d]

    def test_subgraph_many_paths(self, monkeypatch):
        """ https://github.com/conan-io/conan/issues/20457
        """
        layers, width = 6, 3
        grid = [self._nodes(*[f"l{layer}w{w}" for w in range(width)]) for layer in range(layers)]
        top, = self._nodes("top")
        for node in grid[0]:
            self._link(top, node)
        for layer, next_layer in zip(grid, grid[1:]):
            for src in layer:
                for dst in next_layer:
                    self._link(src, dst)

        # We count the number of neighbors calls, which should be 1 per node
        expansions = []
        neighbors = Node.neighbors
        monkeypatch.setattr(Node, "neighbors", lambda x: expansions.append(x) or neighbors(x))

        nodes = top.subgraph().nodes
        assert len(nodes) == layers * width + 1
        assert len(set(nodes)) == len(nodes)
        assert len(expansions) == len(nodes)

    @staticmethod
    def _nodes(*names):
        return [Node(RecipeReference.loads(f"{name}/1.0"), Mock(), context=CONTEXT_HOST)
                for name in names]

    @staticmethod
    def _link(src, dst):
        DepsGraph.add_edge(src, dst, None)
