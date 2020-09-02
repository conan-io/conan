import textwrap
import unittest

from conans.test.utils.tools import TestClient


class PropagateSpecificComponents(unittest.TestCase):
    """
        Feature: recipes can declare the components they are consuming from their requirements,
        only those components should be propagated to their own consumers. If required components
        doesn't exist, Conan will fail:
         * Resolved versions/revisions of the requirement might provide different components or
           no components at all.
    """

    top = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "top"

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["top_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["top_cmp2"]
    """)

    middle = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "middle"
            requires = "top/version"
            def package_info(self):
                self.cpp_info.requires = ["top::cmp1"]
    """)

    @classmethod
    def setUpClass(cls):
        client = TestClient()
        client.save({
            'top.py': cls.top,
            'middle.py': cls.middle
        })
        client.run('create top.py top/version@')
        client.run('create middle.py middle/version@')
        cls.cache_folder = client.cache_folder

    def test_wrong_component(self):
        """ If the requirement doesn't provide the component, it fails """
        t = TestClient(cache_folder=self.cache_folder)
        t.save({'conanfile.py': textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                requires = "top/version"
                def package_info(self):
                    self.cpp_info.requires = ["top::not-existing"]
        """)})
        t.run('create conanfile.py wrong/version@')
        for generator in ['pkg_config', 'cmake_find_package', 'cmake_find_package_multi']:
            t.run('install wrong/version@ -g {}'.format(generator), assert_error=True)
            self.assertIn("ERROR: Component 'top::not-existing' not found in 'top'"
                          " package requirement", t.out)

    def test_cmake_find_package(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.run('install middle/version@ -g cmake_find_package')
        content = t.load('Findmiddle.cmake')
        self.assertIn("find_dependency(top REQUIRED)", content)
        self.assertNotIn("top::top", content)
        self.assertNotIn("top::cmp2", content)
        self.assertIn("top::cmp1", content)

    def test_cmake_find_package_multi(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.run('install middle/version@ -g cmake_find_package_multi')
        content = t.load('middleConfig.cmake')
        self.assertIn("find_dependency(top REQUIRED NO_MODULE)", content)
        self.assertIn("find_package(top REQUIRED NO_MODULE)", content)

        content = t.load('middleTarget-release.cmake')
        self.assertNotIn("top::top", content)
        self.assertNotIn("top::cmp2", content)
        self.assertIn("top::cmp1", content)

    def test_pkg_config(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.run('install middle/version@ -g pkg_config')
        content = t.load('middle.pc')
