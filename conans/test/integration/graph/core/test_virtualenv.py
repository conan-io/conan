import os
import textwrap

from conans.client.generators import VirtualEnvGenerator
from conans.model.ref import ConanFileReference
from conans.test.assets.genconanfile import GenConanfile
from conans.test.integration.graph.core.graph_manager_base import GraphManagerTest


class VirtualEnvGeneratorTestCase(GraphManagerTest):
    """ Check that the declared variables in the ConanFile reach the generator """

    base = textwrap.dedent("""
        import os
        from conans import ConanFile

        class BaseConan(ConanFile):
            name = "base"
            version = "0.1"

            def package_info(self):
                self.env_info.PATH.extend([os.path.join("basedir", "bin"), "samebin"])
                self.env_info.LD_LIBRARY_PATH.append(os.path.join("basedir", "lib"))
                self.env_info.BASE_VAR = "baseValue"
                self.env_info.SPECIAL_VAR = "baseValue"
                self.env_info.BASE_LIST = ["baseValue1", "baseValue2"]
                self.env_info.CPPFLAGS = ["-baseFlag1", "-baseFlag2"]
                self.env_info.BCKW_SLASH = r"base\\value"
    """)

    dummy = textwrap.dedent("""
        import os
        from conans import ConanFile

        class DummyConan(ConanFile):
            name = "dummy"
            version = "0.1"
            requires = "base/0.1"

            def package_info(self):
                self.env_info.PATH = [os.path.join("dummydir", "bin"),"samebin"]
                self.env_info.LD_LIBRARY_PATH.append(os.path.join("dummydir", "lib"))
                self.env_info.SPECIAL_VAR = "dummyValue"
                self.env_info.BASE_LIST = ["dummyValue1", "dummyValue2"]
                self.env_info.CPPFLAGS = ["-flag1", "-flag2"]
                self.env_info.BCKW_SLASH = r"dummy\\value"
    """)

    def test_conanfile(self):
        base_ref = ConanFileReference.loads("base/0.1")
        dummy_ref = ConanFileReference.loads("dummy/0.1")

        self._cache_recipe(base_ref, self.base)
        self._cache_recipe(dummy_ref, self.dummy)
        deps_graph = self.build_graph(GenConanfile().with_requirement(dummy_ref))
        generator = VirtualEnvGenerator(deps_graph.root.conanfile)

        self.assertEqual(generator.env["BASE_LIST"],
                         ['dummyValue1', 'dummyValue2', 'baseValue1', 'baseValue2'])
        self.assertEqual(generator.env["BASE_VAR"], 'baseValue')
        self.assertEqual(generator.env["BCKW_SLASH"], 'dummy\\value')
        self.assertEqual(generator.env["CPPFLAGS"], ['-flag1', '-flag2', '-baseFlag1', '-baseFlag2'])
        self.assertEqual(generator.env["LD_LIBRARY_PATH"],
                         [os.path.join("dummydir", "lib"), os.path.join("basedir", "lib")])
        self.assertEqual(generator.env["PATH"], [os.path.join("dummydir", "bin"),
                                                 os.path.join("basedir", "bin"), 'samebin'])
        self.assertEqual(generator.env["SPECIAL_VAR"], 'dummyValue')
