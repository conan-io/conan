import unittest

from conans.client.conf import default_settings_yml
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver
from conans.client.loader import ConanFileLoader
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.settings import Settings
from conans.model.values import Values
from conans.paths.simple_paths import SimplePaths
from conans.test.unittests.model.fake_retriever import Retriever
from conans.test.unittests.model.transitive_reqs_test import MockSearchRemote
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.tools import TestBufferConanOutput,\
    test_processed_profile
from conans.model.ref import ConanFileReference


class GraphBuilderTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, self.output, ConanPythonRequire(None, None))
        self.retriever = Retriever(self.loader)
        paths = SimplePaths(self.retriever.folder)
        self.remote_search = MockSearchRemote()
        self.resolver = RangeResolver(paths, self.remote_search)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader,
                                        self.resolver, None, None)

    def build_graph(self, content, options="", settings=""):
        self.loader.cached_conanfiles = {}
        full_settings = Settings.loads(default_settings_yml)
        full_settings.values = Values.loads(settings)
        profile = Profile()
        profile.processed_settings = full_settings
        profile.options = OptionsValues.loads(options)
        processed_profile = test_processed_profile(profile=profile)
        root_conan = self.retriever.root(str(content), processed_profile)
        deps_graph = self.builder.load_graph(root_conan, False, False, None, processed_profile)
        return deps_graph

    def test_basic(self):
        deps_graph = self.build_graph(TestConanFile("Say", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self.assertEqual(node.conanfile.name, "Say")
        self.assertEqual(len(node.dependencies), 0)
        self.assertEqual(len(node.dependants), 0)

    def test_transitive(self):
        say_ref = ConanFileReference.loads("Say/0.1@user/testing")
        self.retriever.conan(say_ref, TestConanFile("Say", "0.1"))
        deps_graph = self.build_graph(TestConanFile("Hello", "1.2",
                                                    requires=["Say/0.1@user/testing"]))
        self.assertEqual(2, len(deps_graph.nodes))
        hello = deps_graph.root
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(len(hello.dependencies), 1)
        self.assertEqual(len(hello.dependants), 0)

        say = hello.dependencies[0].dst
        self.assertEqual(say.conanfile.name, "Say")
        self.assertEqual(len(say.dependencies), 0)
        self.assertEqual(len(say.dependants), 1)
        self.assertEqual(say.inverse_neighbors(), [hello])
        self.assertEqual(say.ancestors, set([hello.ref]))
