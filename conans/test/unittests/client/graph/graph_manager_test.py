import os
import unittest


from conans.client.cache.cache import ClientCache
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver
from conans.client.loader import ConanFileLoader
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.unittests.model.transitive_reqs_test import MockSearchRemote
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class GraphManagerTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        cache_folder = temp_folder()
        cache = ClientCache(cache_folder, os.path.join(cache_folder, ".conan"), self.output)
        self.cache = cache
        self.remote_search = MockSearchRemote()
        remote_manager = None
        self.resolver = RangeResolver(cache, self.remote_search)
        proxy = ConanProxy(cache, self.output, remote_manager)
        self.loader = ConanFileLoader(None, self.output, ConanPythonRequire(None, None))
        self.manager = GraphManager(self.output, cache, remote_manager, self.loader, proxy,
                                    self.resolver)

    def _cache_recipe(self, reference, content, revision=None):
        ref = ConanFileReference.loads(reference)
        save(self.cache.conanfile(ref), str(content))
        with self.cache.package_layout(ref).update_metadata() as metadata:
            metadata.recipe.revision = revision or "123"

    def build_graph(self, content, profile_build_requires=None, ref=None):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        save(path, str(content))
        self.loader.cached_conanfiles = {}

        profile = Profile()
        if profile_build_requires:
            profile.build_requires = profile_build_requires
        profile.process_settings(self.cache)
        update = check_updates = False
        workspace = None
        recorder = ActionRecorder()
        remote_name = None
        build_mode = []
        ref = ref or ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile, options, root_ref=ref)
        deps_graph, _ = self.manager.load_graph(path, None, graph_info,
                                                build_mode, check_updates, update,
                                                remote_name, recorder, workspace)
        return deps_graph

    def test_basic(self):
        deps_graph = self.build_graph(TestConanFile("Say", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self.assertEqual(node.conanfile.name, "Say")
        self.assertEqual(len(node.dependencies), 0)
        self.assertEqual(len(node.dependants), 0)

    def test_basic_build_require_recipe(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        deps_graph = self.build_graph(TestConanFile("Hello", "1.2",
                                                    build_requires=["tool/0.1@user/testing"]))

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        hello = deps_graph.root
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(len(hello.dependencies), 1)
        self.assertEqual(len(hello.dependants), 0)

        tool = hello.dependencies[0].dst
        self.assertEqual(tool.conanfile.name, "tool")
        self.assertEqual(len(tool.dependencies), 0)
        self.assertEqual(len(tool.dependants), 1)

    def test_basic_build_require_profile(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        profile_build_requires = {"*": [ConanFileReference.loads("tool/0.1@user/testing")]}
        deps_graph = self.build_graph(TestConanFile("Hello", "1.2"),
                                      profile_build_requires=profile_build_requires)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        hello = deps_graph.root
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(len(hello.dependencies), 1)
        self.assertEqual(len(hello.dependants), 0)

        tool = hello.dependencies[0].dst
        self.assertEqual(tool.conanfile.name, "tool")
        self.assertEqual(len(tool.dependencies), 0)
        self.assertEqual(len(tool.dependants), 1)

    def test_transitive_build_require_recipe(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("Lib", "0.1",
                                         build_requires=["tool/0.1@user/testing"]))
        deps_graph = self.build_graph(TestConanFile("Hello", "1.2",
                                                    requires=["lib/0.1@user/testing"]))

        self.assertEqual(3, len(deps_graph.nodes))
        hello = deps_graph.root
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(len(hello.dependencies), 1)
        self.assertEqual(len(hello.dependants), 0)

        lib = hello.dependencies[0].dst
        self.assertEqual(lib.conanfile.name, "lib")
        self.assertEqual(len(lib.dependencies), 1)
        self.assertEqual(len(lib.dependants), 1)

        tool = lib.dependencies[0].dst
        self.assertEqual(tool.conanfile.name, "tool")
        self.assertEqual(len(tool.dependencies), 0)
        self.assertEqual(len(tool.dependants), 1)

    def test_transitive_build_require_recipe_profile(self):
        self._cache_recipe("mingw/0.1@user/testing", TestConanFile("mingw", "0.1"))
        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("Lib", "0.1",
                                         build_requires=["gtest/0.1@user/testing"]))
        profile_build_requires = {"*": [ConanFileReference.loads("mingw/0.1@user/testing")]}
        deps_graph = self.build_graph(TestConanFile("Hello", "1.2",
                                                    requires=["lib/0.1@user/testing"]),
                                      profile_build_requires=profile_build_requires)

        self.assertEqual(6, len(deps_graph.nodes))
        hello = deps_graph.root
        self.assertEqual(hello.conanfile.name, "Hello")
        self.assertEqual(len(hello.dependencies), 2)
        self.assertEqual(len(hello.dependants), 0)

        lib = hello.dependencies[0].dst
        self.assertEqual(lib.conanfile.name, "lib")
        self.assertEqual(len(lib.dependencies), 2)
        self.assertEqual(len(lib.dependants), 1)

        gtest = lib.dependencies[0].dst
        self.assertEqual(gtest.conanfile.name, "gtest")
        self.assertEqual(len(gtest.dependencies), 1)
        self.assertEqual(len(gtest.dependants), 1)

        mingw_gtest = gtest.dependencies[0].dst
        self.assertEqual(mingw_gtest.conanfile.name, "mingw")
        self.assertEqual(len(mingw_gtest.dependencies), 0)
        self.assertEqual(len(mingw_gtest.dependants), 1)

        mingw_lib = lib.dependencies[1].dst
        self.assertEqual(mingw_lib.conanfile.name, "mingw")
        self.assertEqual(len(mingw_lib.dependencies), 0)
        self.assertEqual(len(mingw_lib.dependants), 1)

        mingw_hello = hello.dependencies[1].dst
        self.assertEqual(mingw_hello.conanfile.name, "mingw")
        self.assertEqual(len(mingw_hello.dependencies), 0)
        self.assertEqual(len(mingw_hello.dependants), 1)
        self.assertNotEqual(id(mingw_hello), id(mingw_lib))
        self.assertNotEqual(id(mingw_hello), id(mingw_gtest))
        self.assertNotEqual(id(mingw_lib), id(mingw_gtest))
