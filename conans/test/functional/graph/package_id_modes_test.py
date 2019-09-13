from conans.client.tools import environment_append
from conans.model.ref import ConanFileReference
from conans.test.functional.graph.graph_manager_base import GraphManagerTest
from conans.test.utils.tools import GenConanfile


class PackageIDGraphTests(GraphManagerTest):

    def test_recipe_modes(self):
        configs = []
        mode = "semver_mode"
        configs.append((mode, "liba/1.1.1@user/testing", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
        configs.append((mode, "liba/1.1.2@user/testing", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
        configs.append((mode, "liba/1.2.1@other/stable", "8ecbf93ba63522ffb32573610c80ab4dcb399b52"))
        mode = "patch_mode"
        configs.append((mode, "liba/1.1.1@user/testing", "bd664570d5174c601d5d417bc19257c4dba48f2e"))
        configs.append((mode, "liba/1.1.2@user/testing", "fb1f766173191d44b67156c6b9ac667422e99286"))
        configs.append((mode, "liba/1.1.1@other/stable", "bd664570d5174c601d5d417bc19257c4dba48f2e"))
        mode = "full_recipe_mode"
        configs.append((mode, "liba/1.1.1@user/testing", "9cbe703e1dee73a2a6807f71d8551c5f1e1b08fd"))
        configs.append((mode, "liba/1.1.2@user/testing", "42a9ff9024adabbd54849331cf01be7d95139948"))
        configs.append((mode, "liba/1.1.1@user/stable", "b41d6c026473cffed4abded4b0eaa453497be1d2"))

        def _assert_recipe_mode(ref_arg, package_id_arg):
            libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
            self._cache_recipe(ref_arg, GenConanfile().with_name("liba").with_version("0.1.1"))
            self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                       .with_require(ref_arg))
            deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                        .with_require(libb_ref))

            self.assertEqual(3, len(deps_graph.nodes))
            app = deps_graph.root
            libb = app.dependencies[0].dst
            liba = libb.dependencies[0].dst

            self.assertEqual(liba.package_id, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
            self.assertEqual(libb.package_id, package_id_arg)

        for package_id_mode, ref, package_id in configs:
            self.cache.config.set_item("general.default_package_id_mode", package_id_mode)
            _assert_recipe_mode(ConanFileReference.loads(ref), package_id)

        for package_id_mode, ref, package_id in configs:
            with environment_append({"CONAN_DEFAULT_PACKAGE_ID_MODE": package_id_mode}):
                _assert_recipe_mode(ConanFileReference.loads(ref), package_id)

    def test_package_revision_mode(self):
        self.cache.config.set_item("general.default_package_id_mode", "package_revision_mode")
        liba_ref1 = ConanFileReference.loads("liba/0.1.1@user/testing")
        libb_ref = ConanFileReference.loads("libb/0.1@user/testing")
        self._cache_recipe(liba_ref1, GenConanfile().with_name("liba").with_version("0.1.1"))
        self._cache_recipe(libb_ref, GenConanfile().with_name("libb").with_version("0.1")
                                                   .with_require(liba_ref1))

        deps_graph = self.build_graph(GenConanfile().with_name("app").with_version("0.1")
                                                    .with_require(libb_ref),
                                      install=False)

        self.assertEqual(3, len(deps_graph.nodes))
        app = deps_graph.root
        libb = app.dependencies[0].dst
        liba = libb.dependencies[0].dst

        self.assertEqual(liba.package_id, "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9")
        self.assertEqual(libb.package_id, "Package_ID_unknown")
