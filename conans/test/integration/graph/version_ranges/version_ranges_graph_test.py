import unittest
from collections import OrderedDict, defaultdict
from collections import namedtuple

from mock import Mock
from parameterized import parameterized

from conans import Settings
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.conf import get_default_settings_yml
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.range_resolver import RangeResolver
from conans.client.loader import ConanFileLoader
from conans.errors import ConanException
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements
from conans.model.values import Values
from conans.test.integration.graph.core.graph_manager_base import MockRemoteManager
from conans.test.unittests.model.fake_retriever import Retriever
from conans.test.utils.mocks import TestBufferConanOutput
from conans.test.utils.tools import GenConanfile, TurboTestClient, TestServer, \
    NO_SETTINGS_PACKAGE_ID
from conans.test.utils.tools import create_profile


class GraphTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, self.output)
        self.retriever = Retriever(self.loader)
        paths = ClientCache(self.retriever.folder, self.output)
        self.remote_manager = MockRemoteManager()
        self.remotes = Remotes()
        self.resolver = RangeResolver(paths, self.remote_manager)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader,
                                        self.resolver)
        cache = Mock()
        cache.config.default_package_id_mode = "semver_direct_mode"
        cache.new_config = defaultdict(Mock)
        self.binaries_analyzer = GraphBinariesAnalyzer(cache, self.output, self.remote_manager)

    def build_graph(self, content, options="", settings=""):
        self.loader._cached_conanfile_classes = {}
        full_settings = Settings.loads(get_default_settings_yml())
        full_settings.values = Values.loads(settings)
        profile = Profile()
        profile.processed_settings = full_settings
        profile.options = OptionsValues.loads(options)
        profile = create_profile(profile=profile)
        root_conan = self.retriever.root(str(content), profile)
        deps_graph = self.builder.load_graph(root_conan, False, False, self.remotes,
                                             profile_host=profile, profile_build=profile)

        build_mode = BuildMode([], self.output)
        self.binaries_analyzer.evaluate_graph(deps_graph, build_mode=build_mode,
                                              update=False, remotes=self.remotes)
        return deps_graph


def _get_nodes(graph, name):
    """ return all the nodes matching a particular name. Could be >1 in case
    that private requirements embed different versions
    """
    return [n for n in graph.nodes if n.conanfile.name == name]


Edge = namedtuple("Edge", "src dst")


def _get_edges(graph):
    edges = set()
    for n in graph.nodes:
        edges.update([Edge(n, neigh) for neigh in n.neighbors()])
    return edges


def _clear_revs(requires):
    for require in requires.values():
        require.ref = require.ref.copy_clear_rev()
    return requires


class VersionRangesTest(GraphTest):

    def setUp(self):
        super(VersionRangesTest, self).setUp()

        for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
            say_content = GenConanfile().with_name("Say").with_version(v)
            say_ref = ConanFileReference.loads("Say/%s@myuser/testing" % v)
            self.retriever.save_recipe(say_ref, say_content)

    def build_graph(self, content, update=False):
        self.loader._cached_conanfile_classes = {}
        profile = create_profile()
        root_conan = self.retriever.root(str(content), profile)
        deps_graph = self.builder.load_graph(root_conan, update, update, self.remotes,
                                             profile_host=profile,
                                             profile_build=profile)
        self.output.write("\n".join(self.resolver.output))
        return deps_graph

    def test_duplicated_error(self):
        content = GenConanfile().with_name("log4cpp").with_version("1.1.1")
        log4cpp_ref = ConanFileReference.loads("log4cpp/1.1.1@myuser/testing")
        self.retriever.save_recipe(log4cpp_ref, content)

        content = """
from conans import ConanFile

class LoggerInterfaceConan(ConanFile):
    name = "LoggerInterface"
    version = "0.1.1"

    def requirements(self):
        self.requires("log4cpp/[~1.1]@myuser/testing")
"""
        logiface_ref = ConanFileReference.loads("LoggerInterface/0.1.1@myuser/testing")
        self.retriever.save_recipe(logiface_ref, content)

        content = """
from conans import ConanFile

class OtherConan(ConanFile):
    name = "other"
    version = "2.0.11549"
    requires = "LoggerInterface/[~0.1]@myuser/testing"
"""
        other_ref = ConanFileReference.loads("other/2.0.11549@myuser/testing")
        self.retriever.save_recipe(other_ref, content)

        content = """
from conans import ConanFile

class Project(ConanFile):
    requires = "LoggerInterface/[~0.1]@myuser/testing", "other/[~2.0]@myuser/testing"
"""
        deps_graph = self.build_graph(content)

        log4cpp = _get_nodes(deps_graph, "log4cpp")[0]
        logger_interface = _get_nodes(deps_graph, "LoggerInterface")[0]
        other = _get_nodes(deps_graph, "other")[0]

        self.assertEqual(4, len(deps_graph.nodes))

        self.assertEqual(log4cpp.ref.copy_clear_rev(), log4cpp_ref)
        conanfile = log4cpp.conanfile
        self.assertEqual(conanfile.version, "1.1.1")
        self.assertEqual(conanfile.name, "log4cpp")

        self.assertEqual(logger_interface.ref.copy_clear_rev(), logiface_ref)
        conanfile = logger_interface.conanfile
        self.assertEqual(conanfile.version, "0.1.1")
        self.assertEqual(conanfile.name, "LoggerInterface")

        self.assertEqual(other.ref.copy_clear_rev(), other_ref)
        conanfile = other.conanfile
        self.assertEqual(conanfile.version, "2.0.11549")
        self.assertEqual(conanfile.name, "other")


