import os
import unittest

from mock import Mock

from conans.client.cache.cache import ClientCache
from conans.client.graph.graph import RECIPE_CONSUMER, RECIPE_INCACHE
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.graph.range_resolver import RangeResolver
from conans.client.installer import BinaryInstaller
from conans.client.loader import ConanFileLoader
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.manifest import FileTreeManifest
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.unittests.model.transitive_reqs_test import MockSearchRemote
from conans.test.utils.conanfile import TestConanFile
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save
from conans.errors import ConanException


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
        hook_manager = Mock()
        recorder = Mock()
        workspace = None
        self.binary_installer = BinaryInstaller(cache, self.output, remote_manager, recorder,
                                                workspace, hook_manager)

    def _cache_recipe(self, reference, test_conanfile, revision=None):
        test_conanfile.info = True
        ref = ConanFileReference.loads(reference)
        save(self.cache.conanfile(ref), str(test_conanfile))
        with self.cache.package_layout(ref).update_metadata() as metadata:
            metadata.recipe.revision = revision or "123"
        manifest = FileTreeManifest.create(self.cache.export(ref))
        manifest.save(self.cache.export(ref))

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
        self.binary_installer.install(deps_graph, False, graph_info)
        return deps_graph

    def test_basic(self):
        deps_graph = self.build_graph(TestConanFile("Say", "0.1"))
        self.assertEqual(1, len(deps_graph.nodes))
        node = deps_graph.root
        self.assertEqual(node.conanfile.name, "Say")
        self.assertEqual(len(node.dependencies), 0)
        self.assertEqual(len(node.dependants), 0)

    def test_transitive(self):
        libb_ref = "libb/0.1@user/testing"
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1"))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=[libb_ref]))
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        self.assertEqual(app.conanfile.name, "app")
        self.assertEqual(len(app.dependencies), 1)
        self.assertEqual(len(app.dependants), 0)
        self.assertEqual(app.recipe, RECIPE_CONSUMER)

        libb = app.dependencies[0].dst
        self.assertEqual(libb.conanfile.name, "libb")
        self.assertEqual(len(libb.dependencies), 0)
        self.assertEqual(len(libb.dependants), 1)
        self.assertEqual(libb.inverse_neighbors(), [app])
        self.assertEqual(libb.ancestors, set([app.ref.name]))
        self.assertEqual(libb.recipe, RECIPE_INCACHE)

        self.assertEqual(app.public_closure, [libb])
        self.assertEqual(libb.public_closure, [])
        self.assertEqual(app.public_deps, {"app": app, "libb": libb})
        self.assertEqual(libb.public_deps, app.public_deps)

    def _check_node(self, node, ref, deps, build_deps, dependents, closure, public_deps):
        conanfile = node.conanfile
        ref = ConanFileReference.loads(str(ref))
        self.assertEqual(node.ref.full_repr(), ref.full_repr())
        self.assertEqual(conanfile.name, ref.name)
        self.assertEqual(len(node.dependencies), len(deps) + len(build_deps))
        self.assertEqual(len(node.dependants), len(dependents))

        public_deps = {n.name: n for n in public_deps}
        self.assertEqual(node.public_deps, public_deps)

        # The recipe requires is resolved to the reference WITH revision!
        self.assertEqual(len(deps), len(conanfile.requires))
        for dep in deps:
            self.assertEqual(conanfile.requires[dep.name].ref,
                             dep.ref)

        self.assertEqual(closure, node.public_closure)
        libs = []
        envs = []
        for n in closure:
            libs.append("mylib%s%slib" % (n.ref.name, n.ref.version))
            envs.append("myenv%s%senv" % (n.ref.name, n.ref.version))
        self.assertEqual(conanfile.deps_cpp_info.libs, libs)
        env = {"MYENV": envs} if envs else {}
        self.assertEqual(conanfile.deps_env_info.vars, env)

    def test_transitive_two_levels(self):
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref]))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@None/None", deps=[libb], build_deps=[], dependents=[],
                         closure=[libb, liba], public_deps=[app, libb, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb], closure=[], public_deps=[app, libb, liba])

    def test_diamond(self):
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref, libc_ref]))

        self.assertEqual(4, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        libc = app.dependencies[1].dst
        liba = libb.dependencies[0].dst

        # No Revision??? Because of consumer?
        self._check_node(app, "app/0.1@None/None", deps=[libb, libc], build_deps=[], dependents=[],
                         closure=[libb, libc, liba], public_deps=[app, libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, libc, liba])
        self._check_node(libb, "libb/0.1@user/testing#123", deps=[liba], build_deps=[],
                         dependents=[app], closure=[liba], public_deps=[app, libb, libc, liba])
        self._check_node(liba, "liba/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[libb, libc], closure=[], public_deps=[app, libb, libc, liba])

    def test_diamond_conflict(self):
        liba_ref = "liba/0.1@user/testing"
        liba_ref2 = "liba/0.2@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1"))
        self._cache_recipe(liba_ref2, TestConanFile("liba", "0.2"))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[liba_ref2]))
        with self.assertRaisesRegexp(ConanException, "Requirement liba/0.2@user/testing conflicts"):
            self.build_graph(TestConanFile("app", "0.1", requires=[libb_ref, libc_ref]))

    def test_loop(self):
        liba_ref = "liba/0.1@user/testing"
        libb_ref = "libb/0.1@user/testing"
        libc_ref = "libc/0.1@user/testing"
        self._cache_recipe(liba_ref, TestConanFile("liba", "0.1", requires=[libc_ref]))
        self._cache_recipe(libb_ref, TestConanFile("libb", "0.1", requires=[liba_ref]))
        self._cache_recipe(libc_ref, TestConanFile("libc", "0.1", requires=[libb_ref]))
        with self.assertRaisesRegexp(ConanException, "Loop detected: 'liba/0.1@user/testing' "
                                     "requires 'libc/0.1@user/testing'"):
            self.build_graph(TestConanFile("app", "0.1", requires=[libc_ref]))

    def test_basic_build_require_recipe(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    build_requires=["tool/0.1@user/testing"]))

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[], build_deps=[tool], dependents=[],
                         closure=[tool], public_deps=[app])
        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[], public_deps=[tool, app])

    def test_basic_build_require_profile(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        profile_build_requires = {"*": [ConanFileReference.loads("tool/0.1@user/testing")]}
        deps_graph = self.build_graph(TestConanFile("app", "0.1"),
                                      profile_build_requires=profile_build_requires)

        # Build requires always apply to the consumer
        self.assertEqual(2, len(deps_graph.nodes))
        app = deps_graph.root
        tool = app.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[], build_deps=[tool], dependents=[],
                         closure=[tool], public_deps=[app])
        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[], public_deps=[tool, app])

    def test_transitive_build_require_recipe(self):
        self._cache_recipe("tool/0.1@user/testing", TestConanFile("tool", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1",
                                         build_requires=["tool/0.1@user/testing"]))
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=["lib/0.1@user/testing"]))

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        tool = lib.dependencies[0].dst

        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib], public_deps=[app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[tool],
                         dependents=[app], closure=[tool], public_deps=[app, lib])

        self._check_node(tool, "tool/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[], public_deps=[tool, lib])

    def test_transitive_build_require_recipe_profile(self):
        self._cache_recipe("mingw/0.1@user/testing", TestConanFile("mingw", "0.1"))
        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1"))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1",
                                         build_requires=["gtest/0.1@user/testing"]))
        profile_build_requires = {"*": [ConanFileReference.loads("mingw/0.1@user/testing")]}
        deps_graph = self.build_graph(TestConanFile("app", "0.1",
                                                    requires=["lib/0.1@user/testing"]),
                                      profile_build_requires=profile_build_requires)

        self.assertEqual(6, len(deps_graph.nodes))
        app = deps_graph.root
        lib = app.dependencies[0].dst
        gtest = lib.dependencies[0].dst
        mingw_gtest = gtest.dependencies[0].dst
        mingw_lib = lib.dependencies[1].dst
        mingw_app = app.dependencies[1].dst

        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[mingw_app], dependents=[],
                         closure=[mingw_app, lib], public_deps=[app, lib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[], build_deps=[mingw_lib, gtest],
                         dependents=[lib], closure=[mingw_lib, gtest], public_deps=[app, lib])
        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[mingw_gtest],
                         dependents=[lib], closure=[mingw_gtest], public_deps=[gtest, lib])
        # MinGW leaf nodes
        self._check_node(mingw_gtest, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[gtest], closure=[], public_deps=[mingw_gtest, gtest])
        self._check_node(mingw_lib, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[lib], closure=[], public_deps=[mingw_lib, gtest, lib])
        self._check_node(mingw_app, "mingw/0.1@user/testing#123", deps=[], build_deps=[],
                         dependents=[app], closure=[], public_deps=[mingw_app, lib, app])

    def test_conflict_transitive_build_requires(self):
        zlib_ref = "zlib/0.1@user/testing"
        zlib_ref2 = "zlib/0.2@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1"))
        self._cache_recipe(zlib_ref2, TestConanFile("zlib", "0.2"))

        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1",
                                                                   requires=[zlib_ref2]))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        with self.assertRaisesRegexp(ConanException, "Requirement zlib/0.2@user/testing conflicts"):
            self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

    def test_not_conflict_transitive_build_requires(self):
        # Same as above, but gtest->(build_require)->zlib2
        zlib_ref = "zlib/0.1@user/testing"
        zlib_ref2 = "zlib/0.2@user/testing"
        self._cache_recipe(zlib_ref, TestConanFile("zlib", "0.1"))
        self._cache_recipe(zlib_ref2, TestConanFile("zlib", "0.2"))

        self._cache_recipe("gtest/0.1@user/testing", TestConanFile("gtest", "0.1",
                                                                   build_requires=[zlib_ref2]))
        self._cache_recipe("lib/0.1@user/testing",
                           TestConanFile("lib", "0.1", requires=[zlib_ref],
                                         build_requires=["gtest/0.1@user/testing"]))

        graph = self.build_graph(TestConanFile("app", "0.1", requires=["lib/0.1@user/testing"]))

        app = graph.root
        lib = app.dependencies[0].dst
        zlib = lib.dependencies[0].dst
        gtest = lib.dependencies[1].dst
        zlib2 = gtest.dependencies[0].dst
        self._check_node(app, "app/0.1@None/None", deps=[lib], build_deps=[], dependents=[],
                         closure=[lib, zlib], public_deps=[app, lib, zlib])

        self._check_node(lib, "lib/0.1@user/testing#123", deps=[zlib], build_deps=[gtest],
                         dependents=[app], closure=[gtest, zlib], public_deps=[app, lib, zlib])

        self._check_node(gtest, "gtest/0.1@user/testing#123", deps=[], build_deps=[zlib2],
                         dependents=[lib], closure=[zlib2], public_deps=[gtest, lib, zlib])
