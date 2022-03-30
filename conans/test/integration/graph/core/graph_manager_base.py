import os
import textwrap
import unittest
from collections import namedtuple

from mock import Mock

from conans.client.cache.cache import ClientCache
from conans.client.cache.remote_registry import Remotes
from conans.client.generators import GeneratorManager
from conans.client.graph.build_mode import BuildMode
from conans.client.graph.graph_binaries import GraphBinariesAnalyzer
from conans.client.graph.graph_manager import GraphManager
from conans.client.graph.proxy import ConanProxy
from conans.client.graph.python_requires import ConanPythonRequire, PyRequireLoader
from conans.client.graph.range_resolver import RangeResolver
from conans.client.installer import BinaryInstaller
from conans.client.loader import ConanFileLoader
from conans.client.recorder.action_recorder import ActionRecorder
from conans.model.graph_info import GraphInfo
from conans.model.manifest import FileTreeManifest
from conans.model.options import OptionsValues
from conans.model.profile import Profile
from conans.model.ref import ConanFileReference
from conans.test.unittests.model.transitive_reqs_test import MockRemoteManager
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import GenConanfile
from conans.test.utils.mocks import TestBufferConanOutput
from conans.util.files import save


class GraphManagerTest(unittest.TestCase):

    def setUp(self):
        self.output = TestBufferConanOutput()
        cache_folder = temp_folder()
        cache = ClientCache(cache_folder, self.output)
        self.cache = cache

    def _get_app(self):
        self.remote_manager = MockRemoteManager()
        cache = self.cache
        self.resolver = RangeResolver(self.cache, self.remote_manager)
        proxy = ConanProxy(cache, self.output, self.remote_manager)
        pyreq_loader = PyRequireLoader(proxy, self.resolver)
        pyreq_loader.enable_remotes(remotes=Remotes())
        self.loader = ConanFileLoader(None, self.output, ConanPythonRequire(None, None),
                                      pyreq_loader=pyreq_loader)
        binaries = GraphBinariesAnalyzer(cache, self.output, self.remote_manager)
        self.manager = GraphManager(self.output, cache, self.remote_manager, self.loader, proxy,
                                    self.resolver, binaries)
        generator_manager = GeneratorManager()
        hook_manager = Mock()
        app_type = namedtuple("ConanApp", "cache out remote_manager hook_manager graph_manager"
                              " binaries_analyzer generator_manager")
        app = app_type(self.cache, self.output, self.remote_manager, hook_manager, self.manager,
                       binaries, generator_manager)
        return app

    def recipe_cache(self, reference, requires=None):
        ref = ConanFileReference.loads(reference)
        conanfile = GenConanfile()
        if requires:
            for r in requires:
                conanfile.with_require(r)
        conanfile.with_package_info(
            cpp_info={"libs": ["mylib{}{}lib".format(ref.name, ref.version)]},
            env_info={"MYENV": ["myenv{}{}env".format(ref.name, ref.version)]})
        self._put_in_cache(ref, conanfile)

    def _put_in_cache(self, ref, conanfile):
        layout = self.cache.package_layout(ref)
        save(layout.conanfile(), str(conanfile))
        # Need to complete de metadata = revision + manifest
        with layout.update_metadata() as metadata:
            metadata.recipe.revision = "123"
        manifest = FileTreeManifest.create(layout.export())
        manifest.save(layout.export())

    def alias_cache(self, alias, target):
        ref = ConanFileReference.loads(alias)
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Alias(ConanFile):
                alias = "%s"
            """ % target)
        self._put_in_cache(ref, conanfile)

    @staticmethod
    def recipe_consumer(reference=None, requires=None, build_requires=None):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        conanfile = GenConanfile()
        if reference:
            ref = ConanFileReference.loads(reference)
            conanfile.with_name(ref.name).with_version(ref.version)
        if requires:
            for r in requires:
                conanfile.with_require(r)
        if build_requires:
            for r in build_requires:
                conanfile.with_build_requires(r)
        save(path, str(conanfile))
        return path

    def _cache_recipe(self, ref, test_conanfile, revision=None):
        if isinstance(test_conanfile, GenConanfile):
            name, version = test_conanfile._name, test_conanfile._version
            test_conanfile = test_conanfile.with_package_info(
                cpp_info={"libs": ["mylib{}{}lib".format(name, version)]},
                env_info={"MYENV": ["myenv{}{}env".format(name, version)]})
        save(self.cache.package_layout(ref).conanfile(), str(test_conanfile))
        with self.cache.package_layout(ref).update_metadata() as metadata:
            metadata.recipe.revision = revision or "123"
        manifest = FileTreeManifest.create(self.cache.package_layout(ref).export())
        manifest.save(self.cache.package_layout(ref).export())

    def build_graph(self, content, profile_build_requires=None, ref=None, create_ref=None,
                    install=True):
        path = temp_folder()
        path = os.path.join(path, "conanfile.py")
        save(path, str(content))
        return self.build_consumer(path, profile_build_requires, ref, create_ref, install)

    def build_consumer(self, path, profile_build_requires=None, ref=None, create_ref=None,
                       install=True):
        profile = Profile()
        if profile_build_requires:
            profile.build_requires = profile_build_requires
        profile.process_settings(self.cache)
        update = check_updates = False
        recorder = ActionRecorder()
        remotes = Remotes()
        build_mode = []  # Means build all
        ref = ref or ConanFileReference(None, None, None, None, validate=False)
        options = OptionsValues()
        graph_info = GraphInfo(profile, options=options, root_ref=ref)
        app = self._get_app()
        deps_graph = app.graph_manager.load_graph(path, create_ref, graph_info, build_mode,
                                                  check_updates, update, remotes, recorder)
        if install:
            binary_installer = BinaryInstaller(app, recorder)
            build_mode = BuildMode(build_mode, app.out)
            binary_installer.install(deps_graph, None, build_mode, update, profile_host=profile,
                                     profile_build=None, graph_lock=None)
        return deps_graph

    def _check_node(self, node, ref, deps=None, build_deps=None, dependents=None, closure=None):
        build_deps = build_deps or []
        dependents = dependents or []
        closure = closure or []
        deps = deps or []

        conanfile = node.conanfile
        ref = ConanFileReference.loads(str(ref))
        self.assertEqual(repr(node.ref), repr(ref))
        self.assertEqual(conanfile.name, ref.name)
        self.assertEqual(len(node.dependencies), len(deps) + len(build_deps))

        dependants = node.inverse_neighbors()
        self.assertEqual(len(dependants), len(dependents))
        for d in dependents:
            self.assertIn(d, dependants)

        # The recipe requires is resolved to the reference WITH revision!
        self.assertEqual(len(deps), len(conanfile.requires))
        for dep in deps:
            self.assertEqual(conanfile.requires[dep.name].ref, dep.ref)

        self.assertEqual(closure, list(node.public_closure))
        libs = []
        envs = []
        for n in closure:
            libs.append("mylib%s%slib" % (n.ref.name, n.ref.version))
            envs.append("myenv%s%senv" % (n.ref.name, n.ref.version))
        self.assertListEqual(list(conanfile.deps_cpp_info.libs), libs)
        env = {"MYENV": envs} if envs else {}
        self.assertEqual(conanfile.deps_env_info.vars, env)
