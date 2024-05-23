import unittest

from mock import Mock

from conans.client.graph.graph import CONTEXT_HOST
from conans.client.graph.graph_builder import DepsGraph, Node
from conans.model.conan_file import ConanFile
from conans.model.recipe_ref import RecipeReference


class DepsGraphTest(unittest.TestCase):

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

        self.assertNotEqual(n1, n2)

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
        self.assertEqual([[n3], [n2], [n1]], deps.by_levels())

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
        self.assertEqual([[n31, n32], [n2], [n1]], deps.by_levels())

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
        self.assertEqual([[n31, n32, n5], [n2], [n1]], deps.by_levels())

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
        self.assertEqual([[n31, n5], [n32], [n2], [n1]], deps.by_levels())
