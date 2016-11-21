import unittest
from conans.test.tools import TestBufferConanOutput
from conans.paths import CONANFILE
import os
from conans.client.deps_builder import DepsBuilder
from conans.model.ref import ConanFileReference
from conans.model.options import OptionsValues
from conans.client.loader import ConanFileLoader
from conans.util.files import save, list_folder_subdirs
from conans.model.settings import Settings
from conans.errors import ConanException
from conans.model.requires import Requirements
from conans.client.conf import default_settings_yml
from conans.model.values import Values
from conans.model.config_dict import undefined_field, bad_value_msg
from conans.test.utils.test_files import temp_folder
from collections import namedtuple
from conans.model.scope import Scopes
from conans.client.require_resolver import RequireResolver
import re


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

    def search(self, pattern):
        print "PATTREN ", pattern
        pattern = str(pattern).replace("@", "/")
        from fnmatch import translate
        pattern = translate(pattern)
        print "TRANSLATED pattern ", pattern
        pattern = re.compile(pattern)

        subdirs = list_folder_subdirs(basedir=self.folder, level=4)
        print "SUBDIRS ", subdirs

        if not pattern:
            result = [ConanFileReference(*folder.split("/")) for folder in subdirs]
        else:
            result = []
            for subdir in subdirs:
                # conan_ref = ConanFileReference(*subdir.split("/"))
                if pattern:
                    if pattern.match(subdir):
                        result.append(subdir)
        print "RESULT ", result
        return sorted(result)

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
    requires = "Say/[whatever]@diego/testing"
"""


hello_ref = ConanFileReference.loads("Hello/1.2@diego/testing")
say_ref = ConanFileReference.loads("Say/0.1@diego/testing")
say_ref2 = ConanFileReference.loads("Say/0.2@diego/testing")


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


class MockSearchRemote(object):
    def search_remotes(self, pattern):
        return


class VersionRangesTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        self.loader = ConanFileLoader(None, Settings.loads(""), OptionsValues.loads(""), Scopes())
        self.retriever = Retriever(self.loader, self.output)
        self.remote_search = MockSearchRemote()
        self.resolver = RequireResolver(self.output, self.retriever, self.remote_search)
        self.builder = DepsBuilder(self.retriever, self.output, self.loader, self.resolver)

    def root(self, content):
        root_conan = self.retriever.root(content)
        deps_graph = self.builder.load(None, root_conan)
        return deps_graph

    def test_basic(self):
        self.retriever.conan(say_ref, say_content)
        deps_graph = self.root(hello_content)

        self.assertEqual(2, len(deps_graph.nodes))
        hello = _get_nodes(deps_graph, "Hello")[0]
        say = _get_nodes(deps_graph, "Say")[0]
        self.assertEqual(_get_edges(deps_graph), {Edge(hello, say)})

        self.assertEqual(hello.conan_ref, None)
        conanfile = hello.conanfile
        self.assertEqual(conanfile.version, "1.2")
        self.assertEqual(conanfile.name, "Hello")
        self.assertEqual(conanfile.requires, Requirements(str(say_ref)))
