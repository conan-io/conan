import unittest
from conans.client.graph.graph_builder import DepsGraph, Node
from conans.model.ref import ConanFileReference
from conans.model.conan_file import ConanFile
from conans.model.settings import Settings


class DepsGraphTest(unittest.TestCase):

    def test_node(self):
        """ nodes are different even if contain same values,
        so they can be repeated if necessary in the graph (common
        static libraries)
        """
        conan_ref1 = ConanFileReference.loads("Hello/0.1@user/stable")
        conan_ref2 = ConanFileReference.loads("Hello/0.1@user/stable")

        conanfile1 = ConanFile(None, None, Settings({}))
        conanfile2 = ConanFile(None, None, Settings({}))
        n1 = Node(conan_ref1, conanfile1)
        n2 = Node(conan_ref2, conanfile2)

        self.assertNotEqual(n1, n2)

    def basic_levels_test(self):
        deps = DepsGraph()
        n1 = Node(1, 1)
        n2 = Node(2, 2)
        n3 = Node(3, 3)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n3)
        deps.add_edge(n1, n2)
        deps.add_edge(n2, n3)
        self.assertEqual([[n3], [n2], [n1]], deps.by_levels())

    def multi_levels_test(self):
        deps = DepsGraph()
        n1 = Node(1, 1)
        n2 = Node(2, 2)
        n31 = Node(31, 31)
        n32 = Node(32, 32)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2)
        deps.add_edge(n2, n31)
        deps.add_edge(n2, n32)
        self.assertEqual([[n31, n32], [n2], [n1]], deps.by_levels())

    def multi_levels_test2(self):
        deps = DepsGraph()
        n1 = Node(1, 1)
        n2 = Node(2, 2)
        n5 = Node(5, 5)
        n31 = Node(31, 31)
        n32 = Node(32, 32)
        deps.add_node(n1)
        deps.add_node(n5)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2)
        deps.add_edge(n1, n5)
        deps.add_edge(n2, n31)
        deps.add_edge(n2, n32)
        self.assertEqual([[n5, n31, n32], [n2], [n1]], deps.by_levels())

    def multi_levels_test3(self):
        deps = DepsGraph()
        n1 = Node(1, 1)
        n2 = Node(2, 2)
        n5 = Node(5, 5)
        n31 = Node(31, 31)
        n32 = Node(32, 32)
        deps.add_node(n1)
        deps.add_node(n5)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2)
        deps.add_edge(n1, n5)
        deps.add_edge(n2, n31)
        deps.add_edge(n2, n32)
        deps.add_edge(n32, n5)
        self.assertEqual([[n5, n31], [n32], [n2], [n1]], deps.by_levels())
