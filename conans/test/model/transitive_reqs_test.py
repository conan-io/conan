import unittest
import os

from collections import namedtuple

from conans.test.utils.tools import TestBufferConanOutput
from conans.paths import CONANFILE
from conans.client.deps_builder import DepsGraphBuilder
from conans.model.ref import ConanFileReference
from conans.model.options import OptionsValues, option_not_exist_msg, option_wrong_value_msg
from conans.client.loader import ConanFileLoader
from conans.util.files import save
from conans.model.settings import Settings, bad_value_msg
from conans.errors import ConanException
from conans.model.requires import Requirements
from conans.client.conf import default_settings_yml
from conans.model.values import Values
from conans.test.utils.test_files import temp_folder
from conans.model.scope import Scopes
from conans.model.profile import Profile


class Retriever(object):
    def __init__(self, loader, output):
        self.loader = loader
        self.output = output
        self.folder = temp_folder()

    def root(self, content):
        conan_path = os.path.join(self.folder, "root")
        save(conan_path, content)
        conanfile = self.loader.load_conan(conan_path, self.output, consumer=True)
        return conanfile

    def conan(self, conan_ref, content):
        if isinstance(conan_ref, str):
            conan_ref = ConanFileReference.loads(conan_ref)
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        save(conan_path, content)

    def get_recipe(self, conan_ref):
        conan_path = os.path.join(self.folder, "/".join(conan_ref), CONANFILE)
        return conan_path

say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
"""

say_content2 = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.2"
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
"""

bye_content = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.1@user/testing"
"""

bye_content2 = """
from conans import ConanFile

class ByeConan(ConanFile):
    name = "Bye"
    version = "0.2"
    requires = "Say/0.2@user/testing"
"""

hello_ref = ConanFileReference.loads("Hello/1.2@user/testing")
say_ref = ConanFileReference.loads("Say/0.1@user/testing")
say_ref2 = ConanFileReference.loads("Say/0.2@user/testing")
chat_ref = ConanFileReference.loads("Chat/2.3@user/testing")
bye_ref = ConanFileReference.loads("Bye/0.2@user/testing")


def _get_nodes(graph, name):
    """ return all the nodes matching a particular name. Could be >1 in case
    that private requirements embed different versions
    """
    return [n for n in graph.nodes if n.conanfile.name == name]


Edge = namedtuple("Edge", "src dst")


def _get_edges(graph):

    edges = set()
    for n in graph.nodes:
        edges.update([Edge(n, neigh) for neigh in graph.neighbors(n)])
    return edges


class MockRequireResolver(object):
    def resolve(self, rquire, conanref):  # @UnusedVariable
        return


class ConanRequirementsTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, Settings.loads(""), Profile())
        self.retriever = Retriever(self.loader, self.output)
        self.builder = DepsGraphBuilder(self.retriever, self.output, self.loader,
                                        MockRequireResolver())

    def root(self, content):
        root_conan = self.retriever.root(content)
        deps_graph = self.builder.load(root_conan)
        return deps_graph

    def test_basic(self):
        deps_graph = self.root(say_content)
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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
        self.retriever.conan(say_ref, say_content)
        deps_graph = self.root(hello_content)
        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

        self.assertEqual(say.conan_ref, say_ref)
        self._check_say(say.conanfile)

    def _check_hello(self, hello, say_ref):
        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "%s/%s" % (say_ref.name, say_ref.version))
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "%s:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9" % str(say_ref))

    def test_transitive_two_levels(self):
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(chat.conan_ref, None)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_no_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(chat.conan_ref, None)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_simple_override(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@user/testing",
               ("Say/0.2@user/testing", "override"))
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_version_requires_change(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"

    def conan_info(self):
        hello_require = self.info.requires["Hello"]
        hello_require.version = hello_require.full_version.minor()
        say_require = self.info.requires["Say"]
        say_require.name = say_require.full_name
        say_require.version = hello_require.full_version.major()
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Hello/1.2.Z\nSay/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_version_requires2_change(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing"

    def conan_info(self):
        self.info.requires["Hello"].full_package_mode()
        self.info.requires["Say"].semver_mode()
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

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
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_conflict_error(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content2)
        self.output.werror_active = True
        with self.assertRaisesRegexp(ConanException, "Conflict in Bye/0.2@user/testing"):
            self.root(chat_content)

    def test_diamond_conflict(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content2)
        deps_graph = self.root(chat_content)

        self.assertIn("""Conflict in Bye/0.2@user/testing
    Requirement Say/0.2@user/testing conflicts with already defined Say/0.1@user/testing
    Keeping Say/0.1@user/testing
    To change it, override it in your base requirements""", self.output)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile)
        self._check_hello(hello, say_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_diamond_conflict_solved(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = ("Hello/1.2@user/testing", "Bye/0.2@user/testing",
                ("Say/0.2@user/testing", "override"))
"""
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content2)
        deps_graph = self.root(chat_content)

        self.assertIn("Hello/1.2@user/testing requirement Say/0.1@user/testing overriden by "
                      "your conanfile to Say/0.2@user/testing", self.output)
        self.assertNotIn("Conflict", self.output)
        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref2)
        self.assertEqual(bye.conan_ref, bye_ref)

        self._check_say(say.conanfile, version="0.2")
        self._check_hello(hello, say_ref2)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref),
                                                          (str(say_ref2), "override")))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(), "")
        self.assertEqual(conaninfo.full_options.dumps(), "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Say/0.2@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_basic_option(self):
        say_content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    options = {"myoption": [123, 234]}
    default_options = "myoption=123"
"""
        deps_graph = self.root(say_content)
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
            self.retriever.conan(say_ref, say_content)
            deps_graph = self.root(conanfile_content)

            self.assertEqual(2, len(deps_graph.nodes))
            hello = _get_nodes(deps_graph, "Hello")[0]
            say = _get_nodes(deps_graph, "Say")[0]
            self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

            self.assertEqual(say.conan_ref, say_ref)
            self._check_say(say.conanfile, options="myoption=234")

            conanfile = hello.conanfile
            self.assertEqual(conanfile.version, "1.2")
            self.assertEqual(conanfile.name, "Hello")
            self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
            self.assertEqual(conanfile.settings.fields, [])
            self.assertEqual(conanfile.settings.values_list, [])
            self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)

        self._check_say(say.conanfile, options="myoption=234")

        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.options.values.dumps(), "Say:myoption=234")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.root(chat_content)
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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)

        with self.assertRaises(ConanException) as cm:
            self.root(chat_content)
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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)

        self.output.werror_active = True
        with self.assertRaisesRegexp(ConanException, "tried to change"):
            self.root(chat_content)

        self.output.werror_active = False
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        bye = _get_nodes(deps_graph, "Bye")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello),
                                                  Edge(bye, say), Edge(chat, bye)})

        self._check_say(say.conanfile, options="myoption=234")
        self.assertIn("Bye/0.2@user/testing tried to change Say/0.1@user/testing "
                      "option myoption to 123 but it was already assigned to 234 "
                      "by Hello/1.2@user/testing", str(self.output).replace("\n", " "))
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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(self.output, "")
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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref),
                                                          str(bye_ref)))

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
        self.retriever.conan(zlib_ref, zlib_content)
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)

        deps_graph = self.root(chat_content)
        self.assertEqual(self.output, "")
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
        self.assertEqual(conanfile.requires, Requirements(str(zlib_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.full_options.dumps(),  "zip=True")
        self.assertEqual(conaninfo.requires.dumps(), "Zlib/2.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Zlib/2.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

        chat_content2 = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"
    default_options = "Say:zip=False"
"""
        deps_graph = self.root(chat_content2)
        self.assertEqual(self.output, "")
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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "Say:zip=False")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_conditional_diamond(self):
        zlib_content = """
from conans import ConanFile

class ZlibConan(ConanFile):
    name = "Zlib"
    version = "0.1"
"""
        png_content = """
from conans import ConanFile

class PngConan(ConanFile):
    name = "png"
    version = "0.1"
"""
        base_content = """
from conans import ConanFile

class BaseConan(ConanFile):
    name = "Base"
    version = "0.1"
"""
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
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "2.3"
    requires = "Say/0.1@user/testing", "Hello/1.2@user/testing"
"""
        zlib_ref = ConanFileReference.loads("Zlib/0.1@user/testing")
        png_ref = ConanFileReference.loads("png/0.1@user/testing")
        base_ref = ConanFileReference.loads("Base/0.1@user/testing")
        self.retriever.conan(zlib_ref, zlib_content)
        self.retriever.conan(base_ref, base_content)
        self.retriever.conan(png_ref, png_content)
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)

        expected = """Say/0.1@user/testing: Incompatible requirements obtained in different evaluations of 'requirements'
    Previous requirements: [Base/0.1@user/testing, Zlib/0.1@user/testing]
    New requirements: [Base/0.1@user/testing, png/0.1@user/testing]"""
        try:
            _ = self.root(chat_content)
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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.conan_ref, say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.2")
        self.assertEqual(say2.conan_ref, say_ref2)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.conan_ref, bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:9d98d1ba7893ef6602e1d629b190a1d2a1100a65\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9\n"
                         "Say/0.2@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

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
        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(say_ref2, say_content2)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

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
        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say1.conanfile.name, "Say")
        self.assertEqual(say1.conanfile.version, "0.1")
        self.assertEqual(say1.conan_ref, say_ref)
        self.assertEqual(say2.conanfile.name, "Say")
        self.assertEqual(say2.conanfile.version, "0.1")
        self.assertEqual(say2.conan_ref, say_ref)
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(bye.conanfile.name, "Bye")
        self.assertEqual(bye.conan_ref, bye_ref)

        conanfile = chat.conanfile
        self.assertEqual(conanfile.version, "2.3")
        self.assertEqual(conanfile.name, "Chat")
        self.assertEqual(conanfile.options.values.dumps(), "")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values.dumps(), "")
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref), str(bye_ref)))

        conaninfo = conanfile.info
        self.assertEqual(conaninfo.settings.dumps(), "")
        self.assertEqual(conaninfo.full_settings.dumps(), "")
        self.assertEqual(conaninfo.options.dumps(),  "")
        self.assertEqual(conaninfo.full_options.dumps(),  "")
        self.assertEqual(conaninfo.requires.dumps(), "Bye/0.2\nHello/1.Y.Z")
        self.assertEqual(conaninfo.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_dep_requires_clear(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"

    def conan_info(self):
        self.info.requires.clear()
"""

        self.retriever.conan(say_ref, say_content)
        deps_graph = self.root(hello_content)

        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conanfile.info.requires.dumps(), "")
        self.assertEqual(hello.conanfile.info.full_requires.dumps(),
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_remove_build_requires(self):
        hello_content = """
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello"
    version = "1.2"
    requires = "Say/0.1@user/testing"

    def conan_info(self):
        self.info.requires.remove("Say")
"""

        self.retriever.conan(say_ref, say_content)
        deps_graph = self.root(hello_content)

        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(hello.conanfile.info.requires.dumps(), "")
        self.assertEqual(hello.conanfile.info.full_requires.dumps(),
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

    def test_remove_two_build_requires(self):
        chat_content = """
from conans import ConanFile

class ChatConan(ConanFile):
    name = "Chat"
    version = "1.2"
    requires = "Hello/1.2@user/testing", "Bye/0.2@user/testing"

    def conan_info(self):
        self.info.requires.remove("Bye", "Hello")
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        self.retriever.conan(bye_ref, bye_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(4, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Bye/0.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")

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

    def conan_info(self):
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

    def conan_info(self):
        if self.options.shared:
            self.info.options["Hello"] = self.info.full_options["Hello"]
            self.info.options["Say"].shared = self.info.full_options["Say"].shared
"""

        self.retriever.conan(say_ref, say_content)
        self.retriever.conan(hello_ref, hello_content)
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:93c0f28f41be7e2dfe12fd6fb93dac72c77cc0d9\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(chat.conanfile.info.options.dumps(),
                         "shared=True\nHello:shared=True\nSay:shared=False")

        # Now change the chat content
        deps_graph = self.root(chat_content.replace("shared=True", "shared=False"))

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:93c0f28f41be7e2dfe12fd6fb93dac72c77cc0d9\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(chat.conanfile.info.options.dumps(), "shared=False")

        # Now change the hello content
        self.retriever.conan(hello_ref, hello_content.replace("shared=True", "shared=False"))
        deps_graph = self.root(chat_content)

        self.assertEqual(3, len(deps_graph.nodes))
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(chat.conanfile.name, "Chat")
        self.assertEqual(chat.conanfile.info.requires.dumps(), "Hello/1.Y.Z")
        self.assertEqual(chat.conanfile.info.full_requires.dumps(),
                         "Hello/1.2@user/testing:0b09634eb446bffb8d3042a3f19d813cfc162b9d\n"
                         "Say/0.1@user/testing:5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(chat.conanfile.info.options.dumps(),
                         "shared=True\nHello:shared=False\nSay:shared=False")


class CoreSettingsTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()

    def root(self, content, options="", settings=""):
        full_settings = Settings.loads(default_settings_yml)
        full_settings.values = Values.loads(settings)
        profile = Profile()
        profile.options = OptionsValues.loads(options)
        loader = ConanFileLoader(None, full_settings, profile)
        retriever = Retriever(loader, self.output)
        builder = DepsGraphBuilder(retriever, self.output, loader, MockRequireResolver())
        root_conan = retriever.root(content)
        deps_graph = builder.load(root_conan)
        return deps_graph

    def test_basic(self):
        content = """
from conans import ConanFile

class SayConan(ConanFile):
    name = "Say"
    version = "0.1"
    settings = "os"
    options = {"myoption": [1, 2, 3]}

    def conan_info(self):
        self.info.settings.os = "Win"
        self.info.options.myoption = "1,2,3"
"""
        deps_graph = self.root(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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

        deps_graph = self.root(content, options="myoption=1", settings="os=Linux")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]

        conanfile = node.conanfile
        check(conanfile, "myoption=1", "os=Linux")

    def test_errors(self):
        with self.assertRaisesRegexp(ConanException, "root: No subclass of ConanFile"):
            self.root("")

        with self.assertRaisesRegexp(ConanException, "root: More than 1 conanfile in the file"):
            self.root("""from conans import ConanFile
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
        deps_graph = self.root(content, options="myoption=2", settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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

        deps_graph = self.root(content, options="myoption=1", settings="os=Linux")
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
        deps_graph = self.root(content, options="arch_independent=True", settings="os=Windows")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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
            self.root(content, options="arch_independent=True", settings="os=Linux")
        self.assertIn(bad_value_msg("settings.os", "Linux",
                                    ['Android', 'FreeBSD', 'Macos', 'SunOS', "Windows", "iOS"]),
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
        deps_graph = self.root(content, settings="os=Windows\n compiler=gcc\narch=x86\n"
                               "compiler.libcxx=libstdc++")
        self.assertIn("WARN: config() has been deprecated. Use config_options and configure",
                      self.output)
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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
        deps_graph = self.root(content, settings="os=Linux")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "header_only=True")
        self.assertNotIn(conanfile.options.values.dumps(), "shared")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.requires, Requirements())

        # in lib mode, there is OS and shared
        deps_graph = self.root(content, settings="os=Linux", options="header_only=False")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
        conanfile = node.conanfile

        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "header_only=False\nshared=False")
        self.assertNotIn(conanfile.options.values.dumps(), "shared")
        self.assertEqual(conanfile.settings.fields, ["os"])
        self.assertEqual(conanfile.requires, Requirements())

        # In windows there is no shared option
        deps_graph = self.root(content, settings="os=Windows", options="header_only=False")
        self.assertEqual(_get_edges(deps_graph), set())
        self.assertEqual(1, len(deps_graph.nodes))
        node = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(node.conan_ref, None)
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
        output = TestBufferConanOutput()
        profile = Profile()
        profile.options = OptionsValues.loads("Say:myoption_say=123\n"
                                              "Hello:myoption_hello=True\n"
                                              "myoption_chat=on")
        loader = ConanFileLoader(None, Settings.loads(""), profile)
        retriever = Retriever(loader, output)
        builder = DepsGraphBuilder(retriever, output, loader, MockRequireResolver())
        retriever.conan(say_ref, say_content)
        retriever.conan(hello_ref, hello_content)

        root_conan = retriever.root(chat_content)
        deps_graph = builder.load(root_conan)

        self.assertEqual(3, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        chat = _get_nodes(deps_graph, "Chat")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say), Edge(chat, hello)})

        self.assertEqual(hello.conan_ref, hello_ref)
        self.assertEqual(say.conan_ref, say_ref)

        conanfile = say.conanfile
        self.assertEqual(conanfile.version, "0.1")
        self.assertEqual(conanfile.name, "Say")
        self.assertEqual(conanfile.options.values.dumps(), "myoption_say=123")
        self.assertEqual(conanfile.settings.fields, [])
        self.assertEqual(conanfile.settings.values_list, [])
        self.assertEqual(conanfile.requires, Requirements())

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
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))

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
        self.assertEqual(conanfile.requires, Requirements(str(hello_ref)))

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
