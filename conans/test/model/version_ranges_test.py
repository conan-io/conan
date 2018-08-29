import unittest
from collections import namedtuple, Counter

from conans.test.utils.tools import TestBufferConanOutput
from conans.paths import SimplePaths
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.model.ref import ConanFileReference
from conans.client.loader import ConanFileLoader, ProcessedProfile
from conans.model.requires import Requirements
from conans.client.graph.range_resolver import RangeResolver, satisfying
from parameterized import parameterized
from conans.errors import ConanException
from conans.test.model.fake_retriever import Retriever
from conans.client.graph.python_requires import ConanPythonRequire


class BasicMaxVersionTest(unittest.TestCase):
    def prereleases_versions_test(self):
        output = TestBufferConanOutput()
        result = satisfying(["1.1.1", "1.1.11", "1.1.21", "1.1.111"], "", output)
        self.assertEqual(result, "1.1.111")
        # prereleases are ordered
        result = satisfying(["1.1.1-a.1", "1.1.1-a.11", "1.1.1-a.111", "1.1.1-a.21"], "~1.1.1-a", output)
        self.assertEqual(result, "1.1.1-a.111")
        result = satisfying(["1.1.1", "1.1.1-11", "1.1.1-111", "1.1.1-21"], "", output)
        self.assertEqual(result, "1.1.1")
        result = satisfying(["4.2.2", "4.2.3-pre"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.3-pre")
        result = satisfying(["4.2.2", "4.2.3-pre", "4.2.4"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.4")
        result = satisfying(["4.2.2", "4.2.3-pre", "4.2.3"], "~4.2.3-", output)
        self.assertEqual(result, "4.2.3")

    def basic_test(self):
        output = TestBufferConanOutput()
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "", output)
        self.assertEqual(result, "2.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "1", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "1.1", output)
        self.assertEqual(result, "1.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], ">1.1", output)
        self.assertEqual(result, "2.1")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "<1.3", output)
        self.assertEqual(result, "1.2")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], "<=1.3", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1", "1.2", "1.3", "2.1"], ">1.1,<2.1", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<1.2", output)
        self.assertEqual(result, "1.1.2")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<1.2.1", output)
        self.assertEqual(result, "1.1.2")
        result = satisfying(["1.1.1", "1.1.2", "1.2.1", "1.3", "2.1"], "<=1.2.1", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.6.1"], ">1.5.0,<1.6.8", output)
        self.assertEqual(result, "1.6.1")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "<=1.2", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "<1.3", output)
        self.assertEqual(result, "1.2.1")
        result = satisfying(["1.a.1", "master", "X.2", "1.2.1", "1.3", "2.1"], "1.3", output)
        self.assertIn("Version 'master' is not semver", output)
        self.assertEqual(result, "1.3")
        result = satisfying(["1.1.1", "1.1.2", "1.2", "1.2.1", "1.3", "2.1"], "1.8||1.3", output)
        self.assertEqual(result, "1.3")

        result = satisfying(["1.3", "1.3.1"], "<1.3", output)
        self.assertEqual(result, None)
        result = satisfying(["1.3.0", "1.3.1"], "<1.3", output)
        self.assertEqual(result, None)
        result = satisfying(["1.3", "1.3.1"], "<=1.3", output)
        self.assertEqual(result, "1.3.1")
        result = satisfying(["1.3.0", "1.3.1"], "<=1.3", output)
        self.assertEqual(result, "1.3.1")
        # >2 means >=3.0.0-0
        result = satisfying(["2.1"], ">2", output)
        self.assertEqual(result, None)
        result = satisfying(["2.1"], ">2.0", output)
        self.assertEqual(result, "2.1")
        # >2.1 means >=2.2.0-0
        result = satisfying(["2.1.1"], ">2.1", output)
        self.assertEqual(result, None)
        result = satisfying(["2.1.1"], ">2.1.0", output)
        self.assertEqual(result, "2.1.1")


hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/[%s]@memsharded/testing"
"""


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


class MockSearchRemote(object):
    def __init__(self, packages=None):
        self.packages = packages or []
        self.count = Counter()

    def search_remotes(self, pattern, ignorecase):  # @UnusedVariable
        self.count[pattern] += 1
        return self.packages


class VersionRangesTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
        self.retriever = Retriever(self.loader, self.output)
        self.remote_search = MockSearchRemote()
        paths = SimplePaths(self.retriever.folder)
        self.resolver = RangeResolver(self.output, paths, self.remote_search)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader, self.resolver, None, None)

        for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
            say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "%s"
""" % v
            say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % v)
            self.retriever.conan(say_ref, say_content)

    def root(self, content, update=False):
        processed_profile = ProcessedProfile()
        root_conan = self.retriever.root(content, processed_profile)
        deps_graph = self.builder.load_graph(root_conan, update, update, None, processed_profile)
        return deps_graph

    def test_local_basic(self):
        for expr, solution in [(">0.0", "2.2.1"),
                               (">0.1,<1", "0.3"),
                               (">0.1,<1||2.1", "2.1"),
                               ("", "2.2.1"),
                               ("~0", "0.3"),
                               ("~=1", "1.2.1"),
                               ("~1.1", "1.1.2"),
                               ("~=2", "2.2.1"),
                               ("~=2.1", "2.1"),
                               ]:
            deps_graph = self.root(hello_content % expr)

            self.assertEqual(2, len(deps_graph.nodes))
            hello = _get_nodes(deps_graph, "Hello")[0]
            say = _get_nodes(deps_graph, "Say")[0]
            self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

            self.assertEqual(hello.conan_ref, None)
            conanfile = hello.conanfile
            self.assertEqual(conanfile.version, "1.2")
            self.assertEqual(conanfile.name, "Hello")
            say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % solution)
            self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

    def test_remote_basic(self):
        self.resolver._local_search = None
        remote_packages = []
        for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
            say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % v)
            remote_packages.append(say_ref)
        self.remote_search.packages = remote_packages
        for expr, solution in [(">0.0", "2.2.1"),
                               (">0.1,<1", "0.3"),
                               (">0.1,<1||2.1", "2.1"),
                               ("", "2.2.1"),
                               ("~0", "0.3"),
                               ("~=1", "1.2.1"),
                               ("~1.1", "1.1.2"),
                               ("~=2", "2.2.1"),
                               ("~=2.1", "2.1"),
                               ]:
            deps_graph = self.root(hello_content % expr, update=True)
            self.assertEqual(self.remote_search.count, {'Say/*@memsharded/testing': 1})
            self.assertEqual(2, len(deps_graph.nodes))
            hello = _get_nodes(deps_graph, "Hello")[0]
            say = _get_nodes(deps_graph, "Say")[0]
            self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

            self.assertEqual(hello.conan_ref, None)
            conanfile = hello.conanfile
            self.assertEqual(conanfile.version, "1.2")
            self.assertEqual(conanfile.name, "Hello")
            say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % solution)
            self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

    def test_remote_optimized(self):
        self.resolver._local_search = None
        remote_packages = []
        for v in ["0.1", "0.2", "0.3", "1.1", "1.1.2", "1.2.1", "2.1", "2.2.1"]:
            say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % v)
            remote_packages.append(say_ref)
        self.remote_search.packages = remote_packages

        dep_content = """from conans import ConanFile
class Dep1Conan(ConanFile):
    requires = "Say/[%s]@memsharded/testing"
"""
        dep_ref = ConanFileReference.loads("Dep1/0.1@memsharded/testing")
        self.retriever.conan(dep_ref, dep_content % ">=0.1")
        dep_ref = ConanFileReference.loads("Dep2/0.1@memsharded/testing")
        self.retriever.conan(dep_ref, dep_content % ">=0.1")

        hello_content = """from conans import ConanFile
class HelloConan(ConanFile):
    name = "Hello"
    requires = "Dep1/0.1@memsharded/testing", "Dep2/0.1@memsharded/testing"
"""
        deps_graph = self.root(hello_content, update=True)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        dep1 = _get_nodes(deps_graph, "Dep1")[0]
        dep2 = _get_nodes(deps_graph, "Dep2")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, dep1), Edge(hello, dep2),
                                                  Edge(dep1, say), Edge(dep2, say)})

        # Most important check: counter of calls to remote
        self.assertEqual(self.remote_search.count, {'Say/*@memsharded/testing': 1})

    @parameterized.expand([("", "0.3", None, None),
                           ('"Say/1.1@memsharded/testing"', "1.1", False, False),
                           ('"Say/0.2@memsharded/testing"', "0.2", False, True),
                           ('("Say/1.1@memsharded/testing", "override")', "1.1", True, False),
                           ('("Say/0.2@memsharded/testing", "override")', "0.2", True, True),
                           # ranges
                           ('"Say/[<=1.2]@memsharded/testing"', "1.2.1", False, False),
                           ('"Say/[>=0.2,<=1.0]@memsharded/testing"', "0.3", False, True),
                           ('("Say/[<=1.2]@memsharded/testing", "override")', "1.2.1", True, False),
                           ('("Say/[>=0.2,<=1.0]@memsharded/testing", "override")', "0.3", True, True),
                           ])
    def transitive_test(self, version_range, solution, override, valid):
        hello_text = hello_content % ">0.1, <1"
        hello_ref = ConanFileReference.loads("Hello/1.2@memsharded/testing")
        self.retriever.conan(hello_ref, hello_text)

        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@memsharded/testing", %s
"""
        if valid is False:
            with self.assertRaisesRegexp(ConanException, "not valid"):
                self.root(chat_content % version_range)
            return

        deps_graph = self.root(chat_content % version_range)
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        edges = {Edge(hello, say), Edge(chat, hello)}
        if override is not None:
            self.assertIn("overridden", self.output)
        else:
            self.assertNotIn("overridden", self.output)
        if override is False:
            edges = {Edge(hello, say), Edge(chat, say), Edge(chat, hello)}

        if valid is True:
            self.assertIn(" valid", self.output)
        elif valid is False:
            self.assertIn("not valid", self.output)
        self.assertEqual(3, len(deps_graph.nodes))

        self.assertEqual(_get_edges(deps_graph), edges)

        self.assertEqual(hello.conan_ref, hello_ref)
        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        say_ref = ConanFileReference.loads("Say/%s@memsharded/testing" % solution)
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

    def duplicated_error_test(self):
        content = """
from conans import ConanFile

class Log3cppConan(ConanFile):
    name = "log4cpp"
    version = "1.1.1"
"""
        log4cpp_ref = ConanFileReference.loads("log4cpp/1.1.1@memsharded/testing")
        self.retriever.conan(log4cpp_ref, content)

        content = """
from conans import ConanFile

class LoggerInterfaceConan(ConanFile):
    name = "LoggerInterface"
    version = "0.1.1"

    def requirements(self):
        self.requires("log4cpp/[~1.1]@memsharded/testing")
"""
        logiface_ref = ConanFileReference.loads("LoggerInterface/0.1.1@memsharded/testing")
        self.retriever.conan(logiface_ref, content)

        content = """
from conans import ConanFile

class OtherConan(ConanFile):
    name = "other"
    version = "2.0.11549"
    requires = "LoggerInterface/[~0.1]@memsharded/testing"
"""
        other_ref = ConanFileReference.loads("other/2.0.11549@memsharded/testing")
        self.retriever.conan(other_ref, content)

        content = """
from conans import ConanFile

class Project(ConanFile):
    requires = "LoggerInterface/[~0.1]@memsharded/testing", "other/[~2.0]@memsharded/testing"
"""
        deps_graph = self.root(content)

        log4cpp = _get_nodes(deps_graph, "log4cpp")[0]
        logger_interface = _get_nodes(deps_graph, "LoggerInterface")[0]
        other = _get_nodes(deps_graph, "other")[0]

        self.assertEqual(4, len(deps_graph.nodes))

        self.assertEqual(log4cpp.conan_ref, log4cpp_ref)
        conanfile = log4cpp.conanfile
        self.assertEqual(conanfile.version, "1.1.1")
        self.assertEqual(conanfile.name, "log4cpp")

        self.assertEqual(logger_interface.conan_ref, logiface_ref)
        conanfile = logger_interface.conanfile
        self.assertEqual(conanfile.version, "0.1.1")
        self.assertEqual(conanfile.name, "LoggerInterface")

        self.assertEqual(other.conan_ref, other_ref)
        conanfile = other.conanfile
        self.assertEqual(conanfile.version, "2.0.11549")
        self.assertEqual(conanfile.name, "other")
