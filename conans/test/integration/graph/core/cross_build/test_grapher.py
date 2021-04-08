import textwrap

from conans.client.graph.grapher import Grapher, Node
from conans.model.profile import Profile
from conans.test.integration.graph.core.cross_build._base_test_case import CrossBuildingBaseTestCase


class GrapherTestCase(CrossBuildingBaseTestCase):
    """ Written on top of the cross-building tests, so I can get a more interesting graph that
        serves for the future when users start to need information related to cross-building
        scenarios.
    """

    application = textwrap.dedent("""
        from conans import ConanFile

        class Protoc(ConanFile):
            name = "application"
            version = "testing"
            url = "http://myurl.com"
            topics = "conan", "center"

            settings = "os"

            def requirements(self):
                self.requires("protobuf/testing@user/channel")

            def build_requirements(self):
                self.build_requires("protoc/testing@user/channel", force_host_context=False)
                # Make it explicit that these should be for host_machine
                self.build_requires("protoc/testing@user/channel", force_host_context=True)
                self.build_requires("gtest/testing@user/channel", force_host_context=True)

    """)

    def setUp(self):
        super(GrapherTestCase, self).setUp()
        self._cache_recipe(self.protobuf_ref, self.protobuf)
        self._cache_recipe(self.protoc_ref, self.protoc)
        self._cache_recipe(self.gtest_ref, self.gtest)
        self._cache_recipe(self.app_ref, self.application)

        profile_host = Profile()
        profile_host.settings["os"] = "Host"
        profile_host.process_settings(self.cache)

        profile_build = Profile()
        profile_build.settings["os"] = "Build"
        profile_build.process_settings(self.cache)

        deps_graph = self._build_graph(profile_host=profile_host, profile_build=profile_build)

        self.grapher = Grapher(deps_graph)

    def test_node_colors(self):
        # Every node gets one color
        for n in self.grapher.nodes:
            color = self.grapher.binary_color(node=n)
            self.assertIsInstance(color, str)

    def test_nodes(self):
        self.assertEqual(len(self.grapher.nodes), 7)
        sorted_nodes = sorted(list(self.grapher.nodes), key=lambda it: (it.label, it.package_id))

        protobuf = sorted_nodes[4]
        self.assertEqual(protobuf.label, "protobuf/testing@user/channel")
        self.assertEqual(protobuf.short_label, "protobuf/testing")
        self.assertEqual(protobuf.package_id, "c31c69c9792316eb5e1a5641419abe169b44f775")
        self.assertEqual(protobuf.is_build_requires, True)
        self.assertEqual(protobuf.binary, "Build")
        self.assertDictEqual(protobuf.data(), {'author': None, 'build_id': None, 'homepage': None,
                                               'license': None, 'topics': None, 'url': None})

        app = sorted_nodes[0]
        self.assertEqual(app.label, "app/testing@user/channel")
        self.assertEqual(app.short_label, "app/testing")
        self.assertEqual(app.package_id, "28220efa62679ebe67eb9e4792449f5e03ef9f8c")
        self.assertEqual(app.is_build_requires, False)
        self.assertEqual(app.binary, "Build")
        self.assertDictEqual(app.data(), {'author': None, 'build_id': None, 'homepage': None,
                                          'license': None, 'topics': ('conan', 'center'),
                                          'url': 'http://myurl.com'})

    def test_edges(self):
        self.assertEqual(len(self.grapher.edges), 7)
        sorted_edges = sorted(list(self.grapher.edges),
                              key=lambda it: (it[0].label, it[0].package_id, it[1].label))

        app_node, gtest_node = sorted_edges[0]
        self.assertIsInstance(app_node, Node)
        self.assertIsInstance(gtest_node, Node)
