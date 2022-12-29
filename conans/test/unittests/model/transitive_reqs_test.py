import unittest
from collections import namedtuple, Counter, defaultdict

import six
from mock import Mock

from conans import DEFAULT_REVISION_V1
from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.conf import get_default_settings_yml
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_builder import DepsGraphBuilder
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver
from conans.client.loader import ConanFileLoader
from conans.errors import ConanException
from conans.model.options import OptionsValues, option_not_exist_msg, option_wrong_value_msg
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.model.requires import Requirements
from conans.model.settings import Settings, bad_value_msg
from conans.model.values import Values
from conans.test.unittests.model.fake_retriever import Retriever
from conans.test.utils.tools import (NO_SETTINGS_PACKAGE_ID, create_profile, GenConanfile)
from conans.test.utils.mocks import TestBufferConanOutput

hello_ref = ConanFileReference.loads("Hello/1.2@user/testing")
say_ref = ConanFileReference.loads("Say/0.1@user/testing")
say_ref2 = ConanFileReference.loads("Say/0.2@user/testing")
chat_ref = ConanFileReference.loads("Chat/2.3@user/testing")
bye_ref = ConanFileReference.loads("Bye/0.2@user/testing")


say_content = GenConanfile().with_name("Say").with_version("0.1")
say_content2 = GenConanfile().with_name("Say").with_version("0.2")
hello_content = GenConanfile().with_name("Hello").with_version("1.2").with_require(say_ref)
chat_content = GenConanfile().with_name("Chat").with_version("2.3").with_require(hello_ref)
bye_content = GenConanfile().with_name("Bye").with_version("0.1").with_require(say_ref)
bye_content2 = GenConanfile().with_name("Bye").with_version("0.2").with_require(say_ref2)


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


class MockRemoteManager(object):
    def __init__(self, packages=None):
        self.packages = packages or []
        self.count = Counter()

    def search_recipes(self, remote, pattern, ignorecase):  # @UnusedVariable
        self.count[pattern] += 1
        return self.packages


class GraphTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, self.output, ConanPythonRequire(None, None))
        self.retriever = Retriever(self.loader)
        paths = ClientCache(self.retriever.folder, self.output)
        self.remote_manager = MockRemoteManager()
        self.remotes = Remotes()
        self.resolver = RangeResolver(paths, self.remote_manager)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader,
                                        self.resolver, None)
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
                                             profile_host=profile, profile_build=None)

        build_mode = BuildMode([], self.output)
        self.binaries_analyzer.evaluate_graph(deps_graph, build_mode=build_mode,
                                              update=False, remotes=self.remotes)
        return deps_graph


class ConanRequirementsTest(GraphTest):

    def test_basic(self):
        deps_graph = self.build_graph(say_content)
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        self._check_say(node.conanfile)

    def _check_say(self, conanfile, version="0.1", options=""):
        self.assertEqual(conanfile.version, version)
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), options)
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values_list, [])
        self.assertEqual(conanfile.requires, Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), options)
        self.assertEqual(conaninfo.full_options.dumps(), options)
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

    def test_transitive(self):
        self.retriever.save_recipe(say_ref, say_content)
        deps_graph = self.build_graph(hello_content)
        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

        self.assertEqual(say.ref.copy_clear_rev(), say_ref)
        self._check_say(say.conanfile)

    def _check_hello(self, hello, say_ref):
        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:%s" % (str(say_ref), NO_SETTINGS_PACKAGE_ID))

    def test_transitive_two_levels(self):
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref)
        self.assertEqual(chat.ref, None)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_diamond_no_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref)
        self.assertEqual(chat.ref, None)
        self.assertEqual(bye.ref.copy_clear_rev(), bye_ref)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_simple_override(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@user/testing",
               ("Say/0.2@user/testing", "override"))
"""

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self._check_say(say.conanfile, version="0.2")
        self._check_hello(hello, say_ref2)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_version_requires_change(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"

    def package_id(self):
        hello_require = self.info.requires["Hello"]
        hello_require.version = hello_require.full_version.minor()
        say_require = self.info.requires["Say"]
        say_require.name = say_require.full_name
        say_require.version = hello_require.full_version.major()
"""

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self._check_say(say.conanfile, version="0.1")
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.2.Z\nSay/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_version_requires2_change(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"

    def package_id(self):
        self.info.requires["Hello"].full_package_mode()
        self.info.requires["Say"].semver_mode()
"""

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self._check_say(say.conanfile, version="0.1")
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_diamond_conflict_error(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content2)
        with six.assertRaisesRegex(self, ConanException, "Conflict in Bye/0.2@user/testing:\n"
                                   "    'Bye/0.2@user/testing' requires 'Say/0.2@user/testing' "
                                   "while 'Hello/1.2@user/testing' requires 'Say/0.1@user/testing'.\n"
                                   "    To fix this conflict you need to override the package 'Say'"
                                   " in your root package."):
            self.build_graph(chat_content)

    def test_diamond_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content2)

        with six.assertRaisesRegex(self, ConanException, "Conflict in Bye/0.2@user/testing:\n"
                                   "    'Bye/0.2@user/testing' requires 'Say/0.2@user/testing'"
                                   " while 'Hello/1.2@user/testing' requires 'Say/0.1@user/testing'.\n"
                                   "    To fix this conflict you need to override the package 'Say'"
                                   " in your root package."):
            self.build_graph(chat_content)

    def test_diamond_conflict_solved(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@user/testing", "Bye/0.2@user/testing",
                ("Say/0.2@user/testing", "override"))
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content2)
        deps_graph = self.build_graph(chat_content)

        self.assertIn("Hello/1.2@user/testing: requirement Say/0.1@user/testing overridden by "
                      "your conanfile to Say/0.2@user/testing", self.output)
        self.assertNotIn("Conflict", self.output)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref2)
        self.assertEqual(bye.ref.copy_clear_rev(), bye_ref)

        self._check_say(say.conanfile, version="0.2")
        self._check_hello(hello, say_ref2)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref), (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_basic_option(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
    default_options = "myoption=123"
"""
        deps_graph = self.build_graph(say_content)
        self.assertEqual(1, len(deps_graph.nodes))
        say = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(_get_edges(deps_graph), set())

        self._check_say(say.conanfile, options="myoption=123")

    def test_basic_transitive_option(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
    default_options = "myoption=123"
"""

        def _assert_conanfile(conanfile_content):
            self.retriever.save_recipe(say_ref, say_content)
            deps_graph = self.build_graph(conanfile_content)

            self.assertEqual(2, len(deps_graph.nodes))
            hello = _get_nodes(deps_graph, "Hello")[0]
            say = _get_nodes(deps_graph, "Say")[0]
            self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

            self.assertEqual(say.ref.copy_clear_rev(), say_ref.copy_clear_rev())
            self._check_say(say.conanfile, options="myoption=234")

            conanfile = hello.conanfile
            self.assertEqual(conanfile.version, "1.2")
            self.assertEqual(conanfile.name, "Hello")
            self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
            self.assertEqual(conanfile.settings.fields, [])
            self.assertEqual(conanfile.settings.values_list, [])
            self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(say_ref)))

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), "")
            self.assertEqual(conaninfo.full_settings.dumps(), "")
            self.assertEqual(conaninfo.options.dumps(), "")
            self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
            self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
            self.assertEqual(conaninfo.full_requires.dumps(),
                             "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d" % str(say_ref))

        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = [("Say:myoption", "234")]  # To test list definition
"""

        _assert_conanfile(hello_content)

        hello_content_tuple = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=234",  # To test tuple definition
"""
        _assert_conanfile(hello_content_tuple)

        hello_content_dict = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = {"Say:myoption" : 234, }  # To test dict definition
"""
        _assert_conanfile(hello_content_dict)

    def test_transitive_two_levels_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    default_options = "Say:myoption=234"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref)

        self._check_say(say.conanfile, options="myoption=234")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d" % str(say_ref))

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "%s:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d"
                         % (str(hello_ref), str(say_ref)))

    def test_transitive_pattern_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    options = {"myoption": [123, 234]}
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    default_options = "*:myoption=234"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref)

        self._check_say(say.conanfile, options="myoption=234")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.options.values.dumps(), "myoption=234\nSay:myoption=234")
        self.assertEqual(conanfile.info.full_options.dumps(), "myoption=234\nSay:myoption=234")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.options.values.dumps(), "Hello:myoption=234\nSay:myoption=234")
        self.assertEqual(conanfile.info.full_options.dumps(), "Hello:myoption=234\nSay:myoption=234")

    def test_transitive_two_levels_wrong_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    default_options = "Say:myoption2=234"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.build_graph(chat_content)
        self.assertEqual(str(cm.exception),
                         "Say/0.1@user/testing: %s" % option_not_exist_msg("myoption2",
                                                                           ['myoption']))

        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    default_options = "Say:myoption=235"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.build_graph(chat_content)
        self.assertEqual(str(cm.exception),  "Say/0.1@user/testing: %s"
                         % option_wrong_value_msg("myoption", "235", ["123", "234"]))

    def test_diamond_no_conflict_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=234"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self._check_say(say.conanfile, options="myoption=234")
        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=234")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:48bb3c5cbdb4822ae87914437ca3cceb733c7e1d")

    def test_diamond_conflict_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=123"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)

        with six.assertRaisesRegex(self, ConanException, "tried to change"):
            self.build_graph(chat_content)

    def test_diamond_conflict_options_solved(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=234"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:myoption=123"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
    default_options = "Say:myoption=123"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})
        self._check_say(say.conanfile, options="myoption=123")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "Say:myoption=123")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:e736d892567343489b1360fde797ad18a2911920")

    def test_conditional(self):
        zlib_content = """
from conans import ConanFile

class ZlibConan(ConanFile):
    name = "Zlib"
    version = "2.1"
"""
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"zip": [True, False]}

    def requirements(self):
        if self.options.zip:
            self.requires("Zlib/2.1@user/testing")
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:zip=True"
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
    default_options = "Say:zip=True"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        zlib_ref = ConanFileReference.loads("Zlib/2.1@user/testing")
        self.retriever.save_recipe(zlib_ref, zlib_content)
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)

        deps_graph = self.build_graph(chat_content)
        self.assertEqual(5, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        zlib = _get_nodes(deps_graph, "Zlib")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say),
                                                  Edge(chat, bye), Edge(say, zlib)})

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "zip=True")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str("%s#%s" % (zlib_ref,
                                                                         DEFAULT_REVISION_V1))))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.full_options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.requires.dumps(), "Zlib/2.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Zlib/2.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

        chat_content2 = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
    default_options = "Say:zip=False"
"""
        deps_graph = self.build_graph(chat_content2)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "zip=False")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "zip=False")
        self.assertEqual(conaninfo.full_options.dumps(),  "zip=False")
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "Say:zip=False")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         _clear_revs(Requirements(str(hello_ref), str(bye_ref))))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "Say:zip=False")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_conditional_diamond(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"zip": [True, False]}
    default_options = "zip=False"
    requires = "Base/0.1@user/testing"

    def requirements(self):
        if self.options.zip:
            self.requires("Zlib/0.1@user/testing")
        else:
            self.requires("png/0.1@user/testing")
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    requires = "Say/0.1@user/testing"
    default_options = "Say:zip=True"
"""
        zlib_ref = ConanFileReference.loads("Zlib/0.1@user/testing")
        png_ref = ConanFileReference.loads("png/0.1@user/testing")
        base_ref = ConanFileReference.loads("Base/0.1@user/testing")
        self.retriever.save_recipe(zlib_ref, GenConanfile().with_name("ZLib").with_version("0.1"))
        self.retriever.save_recipe(base_ref, GenConanfile().with_name("Base").with_version("0.1"))
        self.retriever.save_recipe(png_ref, GenConanfile().with_name("png").with_version("0.1"))
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)

        expected = """Say/0.1@user/testing: Incompatible requirements obtained in different evaluations of 'requirements'
    Previous requirements: [Base/0.1@user/testing, png/0.1@user/testing]
    New requirements: [Base/0.1@user/testing, Zlib/0.1@user/testing]"""
        try:
            self.build_graph(GenConanfile().with_name("Chat").with_version("2.3")
                                           .with_require(say_ref)
                                           .with_require(hello_ref))
            self.assert_(False, "Exception not thrown")
        except ConanException as e:
            self.assertEqual(str(e), expected)

    def test_transitive_private(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "0.1"
    requires = ("Say/0.1@user/testing", "private"),
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = ("Say/0.2@user/testing", "private"),
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(5, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say_nodes = sorted(_get_nodes(deps_graph, "Say"))
        say1 = say_nodes[0]
        say2 = say_nodes[1]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say1), Edge(chat, hello),
                                                  Edge(bye, say2), Edge(chat, bye)})
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.ref.copy_clear_rev(), say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.2")
        self.assertEqual(say2.ref.copy_clear_rev(), say_ref2)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.ref.copy_clear_rev(), bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s\n"
                         "Say/0.2@user/testing:%s" % (NO_SETTINGS_PACKAGE_ID,
                                                      NO_SETTINGS_PACKAGE_ID))

    def test_transitive_diamond_private(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = ("Say/0.1@user/testing", "private"),
"""
        bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(say_ref2, say_content2)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(5, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say_nodes = sorted(_get_nodes(deps_graph, "Say"))
        say1 = say_nodes[0]
        say2 = say_nodes[1]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertTrue((_get_edges(deps_graph) == {Edge(hello, say1), Edge(chat, hello),
                                                    Edge(bye, say2), Edge(chat, bye)}) or
                        (_get_edges(deps_graph) == {Edge(hello, say2), Edge(chat, hello),
                                                    Edge(bye, say1), Edge(chat, bye)})
                        )
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.ref.copy_clear_rev(), say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.1")
        self.assertEqual(say2.ref.copy_clear_rev(), say_ref)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.ref.copy_clear_rev(), bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires),
                         Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_dep_requires_clear(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"

    def package_id(self):
        self.info.requires.clear()
"""

        self.retriever.save_recipe(say_ref, say_content)
        deps_graph = self.build_graph(hello_content)

        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conanfile.info.requires.dumps(), "")
        self.assertEqual(hello.conanfile.info.full_requires.dumps(),
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_remove_requires(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"

    def package_id(self):
        self.info.requires.remove("Say")
"""

        self.retriever.save_recipe(say_ref, say_content)
        deps_graph = self.build_graph(hello_content)

        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conanfile.info.requires.dumps(), "")
        self.assertEqual(hello.conanfile.info.full_requires.dumps(),
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_remove_two_requires(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "1.2"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"

    def package_id(self):
        self.info.requires.remove("Bye", "Hello")
"""

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        self.retriever.save_recipe(bye_ref, bye_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)

    def test_propagate_indirect_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"shared": [True, False]}
    default_options = "shared=False"
"""

        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    options = {"shared": [True, False]}
    default_options = "shared=True"

    def package_id(self):
        if self.options.shared:
            self.info.options["Say"] = self.info.full_options["Say"]
"""

        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    options = {"shared": [True, False]}
    default_options = "shared=True"

    def package_id(self):
        if self.options.shared:
            self.info.options["Hello"] = self.info.full_options["Hello"]
            self.info.options["Say"].shared = self.info.full_options["Say"].shared
"""

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:93c0f28f41be7e2dfe12fd6fb93dac72c77cc0d9\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertEqual(chat.conanfile.info.options.dumps(),
                         "shared=True\nHello:shared=True\nSay:shared=False")

        # Now change the chat content
        deps_graph = self.build_graph(chat_content.replace("shared=True", "shared=False"))

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:93c0f28f41be7e2dfe12fd6fb93dac72c77cc0d9\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertEqual(chat.conanfile.info.options.dumps(), "shared=False")

        # Now change the hello content
        self.retriever.save_recipe(hello_ref, hello_content.replace("shared=True", "shared=False"))
        deps_graph = self.build_graph(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID)
        self.assertEqual(chat.conanfile.info.options.dumps(),
                         "shared=True\nHello:shared=False\nSay:shared=False")


class ConanRequirementsOptimizerTest(unittest.TestCase):
    liba_content = """
from conans import ConanFile

class LibAConan(ConanFile):
    name = "LibA"
    options = {"shared": [True, False]}
    default_options = "shared=False"
    def requirements(self):
        self.output.info("LibA requirements()")
    def configure(self):
        self.output.info("LibA configure()")
"""
    libb_content = """
from conans import ConanFile

class LibBConan(ConanFile):
    name = "LibB"
    version = "0.1"
    requires = "LibA/0.1@user/testing"
"""
    libc_content = """
from conans import ConanFile

class LibCConan(ConanFile):
    name = "LibC"
    version = "0.1"
    requires = "LibB/0.1@user/testing"
"""
    libd_content = """
from conans import ConanFile

class LibDConan(ConanFile):
    name = "LibD"
    version = "0.1"
    requires = "LibB/0.1@user/testing"
"""
    consumer_content = """
from conans import ConanFile

class ConsumerConan(ConanFile):
    requires = "LibC/0.1@user/testing", "LibD/0.1@user/testing"
"""

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, self.output, ConanPythonRequire(None, None))
        self.retriever = Retriever(self.loader)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader,
                                        Mock(), None)
        liba_ref = ConanFileReference.loads("LibA/0.1@user/testing")
        liba2_ref = ConanFileReference.loads("LibA/0.2@user/testing")
        libb_ref = ConanFileReference.loads("LibB/0.1@user/testing")
        libc_ref = ConanFileReference.loads("LibC/0.1@user/testing")
        libd_ref = ConanFileReference.loads("LibD/0.1@user/testing")
        self.retriever.save_recipe(liba_ref, self.liba_content)
        # It is necessary to create libA/0.2 to have a conflict, otherwise it is missing
        self.retriever.save_recipe(liba2_ref, self.liba_content)
        self.retriever.save_recipe(libb_ref, self.libb_content)
        self.retriever.save_recipe(libc_ref, self.libc_content)
        self.retriever.save_recipe(libd_ref, self.libd_content)

    def build_graph(self, content):
        profile = create_profile()
        root_conan = self.retriever.root(content, profile)
        deps_graph = self.builder.load_graph(root_conan, False, False, None,
                                             profile_host=profile, profile_build=None)
        return deps_graph

    def test_avoid_duplicate_expansion(self):
        self.build_graph(self.consumer_content)
        self.assertEqual(1, str(self.output).count("LibA requirements()"))
        self.assertEqual(1, str(self.output).count("LibA configure()"))

    def test_expand_requirements(self):
        libd_content = """
from conans import ConanFile

class LibDConan(ConanFile):
    name = "LibD"
    version = "0.1"
    requires = "LibB/0.1@user/testing", ("LibA/0.2@user/testing", "override")
"""
        libd_ref = ConanFileReference.loads("LibD/0.1@user/testing")
        self.retriever.save_recipe(libd_ref, libd_content)

        with six.assertRaisesRegex(self, ConanException, "Conflict in LibB/0.1@user/testing:\n"
                                   "    'LibB/0.1@user/testing' requires 'LibA/0.2@user/testing' "
                                   "while 'LibB/0.1@user/testing' requires 'LibA/0.1@user/testing'.\n"
                                   "    To fix this conflict you need to override the package 'LibA' "
                                   "in your root package."):
            self.build_graph(self.consumer_content)
        self.assertIn("LibB/0.1@user/testing: requirement LibA/0.1@user/testing overridden by "
                      "LibD/0.1@user/testing to LibA/0.2@user/testing", str(self.output))
        self.assertEqual(1, str(self.output).count("LibA requirements()"))
        self.assertEqual(1, str(self.output).count("LibA configure()"))

    def test_expand_requirements_direct(self):
        libd_content = """
from conans import ConanFile

class LibDConan(ConanFile):
    name = "LibD"
    version = "0.1"
    requires = "LibB/0.1@user/testing", "LibA/0.2@user/testing"
"""
        libd_ref = ConanFileReference.loads("LibD/0.1@user/testing")
        self.retriever.save_recipe(libd_ref, libd_content)

        with six.assertRaisesRegex(self, ConanException, "Conflict in LibB/0.1@user/testing:\n"
                                   "    'LibB/0.1@user/testing' requires 'LibA/0.2@user/testing' "
                                   "while 'LibB/0.1@user/testing' requires 'LibA/0.1@user/testing'.\n"
                                   "    To fix this conflict you need to override the package 'LibA' in "
                                   "your root package."):
            self.build_graph(self.consumer_content)
        self.assertEqual(1, str(self.output).count("LibA requirements()"))
        self.assertEqual(1, str(self.output).count("LibA configure()"))

    def test_expand_options(self):
        """ if only one path changes the default option, it has to be expanded
        upstream, as things might change
        """
        libd_content = """
from conans import ConanFile

class LibDConan(ConanFile):
    name = "LibD"
    version = "0.1"
    requires = "LibB/0.1@user/testing"
    default_options = "LibA:shared=True"
"""
        libd_ref = ConanFileReference.loads("LibD/0.1@user/testing")
        self.retriever.save_recipe(libd_ref, libd_content)

        self.build_graph(self.consumer_content)
        self.assertEqual(2, str(self.output).count("LibA requirements()"))
        self.assertEqual(2, str(self.output).count("LibA configure()"))

    def test_expand_conflict_options(self):
        """ if one of the nodes causes an explicit conflict of options,
        then, the other downstream is discarded there, no need to propagate twice
        upstream
        """
        libb_ref = ConanFileReference.loads("LibB/0.1@user/testing")
        libd_ref = ConanFileReference.loads("LibD/0.1@user/testing")
        libc_ref = ConanFileReference.loads("LibC/0.1@user/testing")

        self.retriever.save_recipe(libd_ref, GenConanfile().with_name("LibD").with_version("0.1")
                                                           .with_require(libb_ref)
                                                           .with_default_option("LibA:shared", True))
        self.retriever.save_recipe(libc_ref, GenConanfile().with_name("LibC").with_version("0.1")
                                                           .with_require(libb_ref)
                                                           .with_default_option("LibA:shared", False))

        with six.assertRaisesRegex(self, ConanException,
                                   "LibD/0.1@user/testing tried to change LibB/0.1@user/testing "
                                   "option LibA:shared to True"):
            self.build_graph(self.consumer_content)

        self.assertEqual(1, str(self.output).count("LibA requirements()"))
        self.assertEqual(1, str(self.output).count("LibA configure()"))


class CoreSettingsTest(GraphTest):

    def test_basic(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"myoption": [1, 2, 3]}

    def package_id(self):
        self.info.settings.os = "Win"
        self.info.options.myoption = "1,2,3"
"""
        deps_graph = self.build_graph(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), "os=Win")
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), "myoption=1,2,3")
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

            self.assertEqual(conaninfo.package_id(), "6a3d66035e2dcbcfd16d5541b40785c01487c2f9")

        check(conanfile, "myoption=2", "os=Windows")

        deps_graph = self.build_graph(content, options="myoption=1", settings="os=Linux")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]

        conanfile = node.conanfile
        check(conanfile, "myoption=1", "os=Linux")

    def test_errors(self):
        with six.assertRaisesRegex(self, ConanException, "root.py: No subclass of ConanFile"):
            self.build_graph("")

        with six.assertRaisesRegex(self, ConanException,
                                   "root.py: More than 1 conanfile in the file"):
            self.build_graph("""from conans import ConanFile
class HelloConan(ConanFile):pass
class ByeConan(ConanFile):pass""")

    def test_config(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"myoption": [1, 2, 3]}

    def config(self):
        if self.settings.os == "Linux":
            self.options.clear()
"""
        deps_graph = self.build_graph(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), settings)
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), options)
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

        check(conanfile, "myoption=2", "os=Windows")

        deps_graph = self.build_graph(content, options="myoption=1", settings="os=Linux")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]

        conanfile = node.conanfile
        check(conanfile, "", "os=Linux")

    def test_config_remove(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "arch"
    options = {"arch_independent": [True, False]}

    def config(self):
        if self.options.arch_independent:
            self.settings.remove("arch")
            self.settings.os.remove("Linux")
"""
        deps_graph = self.build_graph(content, options="arch_independent=True",
                                      settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        def check(conanfile, options, settings):
            self.assertEqual(conanfile.version, "0.1")
            self.assertEqual(conanfile.name, "Say")
            self.assertEqual(conanfile.options.values.dumps(), options)
            self.assertEqual(conanfile.settings.fields, ["os"])
            self.assertEqual(conanfile.settings.values.dumps(), settings)
            self.assertEqual(conanfile.requires, Requirements())

            conaninfo = conanfile.info
            self.assertEqual(conaninfo.settings.dumps(), settings)
            self.assertEqual(conaninfo.full_settings.dumps(), settings)
            self.assertEqual(conaninfo.options.dumps(), options)
            self.assertEqual(conaninfo.full_options.dumps(), options)
            self.assertEqual(conaninfo.requires.dumps(), "")
            self.assertEqual(conaninfo.full_requires.dumps(), "")

        check(conanfile, "arch_independent=True", "os=Windows")

        with self.assertRaises(ConanException) as cm:
            self.build_graph(content, options="arch_independent=True", settings="os=Linux")
        self.assertIn(bad_value_msg("settings.os", "Linux",
                                    ['AIX', 'Android', 'Arduino', 'Emscripten', 'FreeBSD', 'Macos',
                                     'Neutrino', 'SunOS', 'VxWorks', 'Windows', 'WindowsCE',
                                     'WindowsStore', 'baremetal', 'iOS', 'tvOS', 'watchOS']),
                      str(cm.exception))

    def test_config_remove2(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os", "arch", "compiler"

    def config(self):
        del self.settings.compiler.version
"""
        deps_graph = self.build_graph(content, settings="os=Windows\n compiler=gcc\narch=x86\n"
                                      "compiler.libcxx=libstdc++")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, ["arch", "compiler", "os"])
        self.assertNotIn("compiler.version", conanfile.settings.values.dumps())
        self.assertEqual(conanfile.requires, Requirements())

    def test_new_configure(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"shared": [True, False], "header_only": [True, False],}
    default_options = "shared=False", "header_only=True"

    def config_options(self):
        if self.settings.os == "Windows":
            del self.options.shared

    def configure(self):
        if self.options.header_only:
            self.settings.clear()
            del self.options.shared
"""
        deps_graph = self.build_graph(content, settings="os=Linux")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "header_only=True")
        self.assertNotIn(conanfile.options.values.dumps(), "shared")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.requires, Requirements())

        # in lib mode, there is OS and shared
        deps_graph = self.build_graph(content, settings="os=Linux", options="header_only=False")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "header_only=False\nshared=False")
        self.assertNotIn(conanfile.options.values.dumps(), "shared")
        self.assertEqual(conanfile.settings.fields, ["os"])
        self.assertEqual(conanfile.requires, Requirements())

        # In windows there is no shared option
        deps_graph = self.build_graph(content, settings="os=Windows", options="header_only=False")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "header_only=False")
        self.assertNotIn(conanfile.options.values.dumps(), "shared")
        self.assertEqual(conanfile.settings.fields, ["os"])
        self.assertEqual(conanfile.requires, Requirements())

    def test_transitive_two_levels_options(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption_say": [123, 234]}
"""
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"
    options = {"myoption_hello": [True, False]}
"""
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"
    options = {"myoption_chat": ["on", "off"]}
"""
        profile = Profile()
        profile.processed_settings = Settings()
        profile.options = OptionsValues.loads("Say:myoption_say=123\n"
                                              "Hello:myoption_hello=True\n"
                                              "myoption_chat=on")

        self.retriever.save_recipe(say_ref, say_content)
        self.retriever.save_recipe(hello_ref, hello_content)

        profile = create_profile(profile=profile)
        root_conan = self.retriever.root(chat_content, profile)
        deps_graph = self.builder.load_graph(root_conan, False, False, None,
                                             profile_host=profile, profile_build=None)

        build_mode = BuildMode([], self.output)
        self.binaries_analyzer.evaluate_graph(deps_graph, build_mode=build_mode,
                                              update=False, remotes=None)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.ref.copy_clear_rev(), hello_ref)
        self.assertEqual(say.ref.copy_clear_rev(), say_ref)

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values_list, [])
        self.assertEqual(_clear_revs(conanfile.requires), Requirements())

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_say=123")
        self.assertEqual(conaninfo.full_options.dumps(), "myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "")
        self.assertEqual(conaninfo.full_requires.dumps(), "")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(),
                         "myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_hello=True")
        self.assertEqual(conaninfo.full_options.dumps(),
                         "myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:751fd69d10b2a54fdd8610cdae748d6b22700841" % str(say_ref))

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(),
                         "myoption_chat=on\nHello:myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(_clear_revs(conanfile.requires), Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "myoption_chat=on")
        self.assertEqual(conaninfo.full_options.dumps(),
                         "myoption_chat=on\nHello:myoption_hello=True\nSay:myoption_say=123")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:95c360996106af45b8eec11a37df19fda39a5880\n"
                         "%s:751fd69d10b2a54fdd8610cdae748d6b22700841"
                         % (str(hello_ref), str(say_ref)))
