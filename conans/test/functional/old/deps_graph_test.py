import unittest

from conans.client.graph.graph_builder import DepsGraph, Node
from conans.model.conan_file import ConanFile
from conans.model.ref import ConanFileReference
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
        ref1 = ConanFileReference.loads("Hello/1.0@user/stable")
        ref2 = ConanFileReference.loads("Hello/2.0@user/stable")
        ref3 = ConanFileReference.loads("Hello/3.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, 1)
        n2 = Node(ref2, 2)
        n3 = Node(ref3, 3)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n3)
        deps.add_edge(n1, n2)
        deps.add_edge(n2, n3)
        self.assertEqual([[n3], [n2], [n1]], deps.by_levels())

    def multi_levels_test(self):
        ref1 = ConanFileReference.loads("Hello/1.0@user/stable")
        ref2 = ConanFileReference.loads("Hello/2.0@user/stable")
        ref31 = ConanFileReference.loads("Hello/31.0@user/stable")
        ref32 = ConanFileReference.loads("Hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, 1)
        n2 = Node(ref2, 2)
        n31 = Node(ref31, 31)
        n32 = Node(ref32, 32)
        deps.add_node(n1)
        deps.add_node(n2)
        deps.add_node(n32)
        deps.add_node(n31)
        deps.add_edge(n1, n2)
        deps.add_edge(n2, n31)
        deps.add_edge(n2, n32)
        self.assertEqual([[n31, n32], [n2], [n1]], deps.by_levels())

    def multi_levels_test2(self):

        ref1 = ConanFileReference.loads("Hello/1.0@user/stable")
        ref2 = ConanFileReference.loads("Hello/2.0@user/stable")
        ref5 = ConanFileReference.loads("Hello/5.0@user/stable")
        ref31 = ConanFileReference.loads("Hello/31.0@user/stable")
        ref32 = ConanFileReference.loads("Hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, 1)
        n2 = Node(ref2, 2)
        n5 = Node(ref5, 5)
        n31 = Node(ref31, 31)
        n32 = Node(ref32, 32)
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

        ref1 = ConanFileReference.loads("Hello/1.0@user/stable")
        ref2 = ConanFileReference.loads("Hello/2.0@user/stable")
        ref5 = ConanFileReference.loads("Hello/5.0@user/stable")
        ref31 = ConanFileReference.loads("Hello/31.0@user/stable")
        ref32 = ConanFileReference.loads("Hello/32.0@user/stable")

        deps = DepsGraph()
        n1 = Node(ref1, 1)
        n2 = Node(ref2, 2)
        n5 = Node(ref5, 5)
        n31 = Node(ref31, 31)
        n32 = Node(ref32, 32)
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
