import unittest
from conans.client.deps_builder import DepsGraph, Node
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
        deps.add_node(1)
        deps.add_node(2)
        deps.add_node(3)
        deps.add_edge(1, 2)
        deps.add_edge(2, 3)
        self.assertEqual([[3], [2], [1]], deps.by_levels())

    def multi_levels_test(self):
        deps = DepsGraph()
        deps.add_node(1)
        deps.add_node(2)
        deps.add_node(32)
        deps.add_node(31)
        deps.add_edge(1, 2)
        deps.add_edge(2, 31)
        deps.add_edge(2, 32)
        self.assertEqual([[31, 32], [2], [1]], deps.by_levels())

    def multi_levels_test2(self):
        deps = DepsGraph()
        deps.add_node(1)
        deps.add_node(5)
        deps.add_node(2)
        deps.add_node(32)
        deps.add_node(31)
        deps.add_edge(1, 2)
        deps.add_edge(1, 5)
        deps.add_edge(2, 31)
        deps.add_edge(2, 32)
        self.assertEqual([[5, 31, 32], [2], [1]], deps.by_levels())

    def multi_levels_test3(self):
        deps = DepsGraph()
        deps.add_node(1)
        deps.add_node(5)
        deps.add_node(2)
        deps.add_node(32)
        deps.add_node(31)
        deps.add_edge(1, 2)
        deps.add_edge(1, 5)
        deps.add_edge(2, 31)
        deps.add_edge(2, 32)
        deps.add_edge(32, 5)
        self.assertEqual([[5, 31], [32], [2], [1]], deps.by_levels())
