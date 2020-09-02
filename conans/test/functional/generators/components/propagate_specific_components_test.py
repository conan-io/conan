import unittest
import textwrap
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
        cf = '/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmpa6tmtp3nconans/path with spaces'
        t = TestClient(cache_folder=self.cache_folder, current_folder=cf)
        t.save({'conanfile.py': textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                requires = "top/version"
                def package_info(self):
                    self.cpp_info.requires = ["top::wrong"]
        """)})
        t.run('create conanfile.py wrong/version@')
        t.run('install wrong/version@ -g cmake_find_package')
        self.assertIn('TODO: Define message here', t.out)

    def test_cmake_find_package(self):
        cf = '/private/var/folders/fc/6mvcrc952dqcjfhl4c7c11ph0000gn/T/tmpn_ig2dbcconans/path with spaces'
        t = TestClient(cache_folder=self.cache_folder, current_folder=cf)
        t.run('install middle/version@ -g cmake_find_package')
        c = t.load('Findmiddle.cmake')
        print(c)
        self.fail("AAA")
