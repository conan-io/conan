import textwrap
import unittest

import pytest

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

    app = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            settings = "os", "compiler", "build_type", "arch"
            name = "app"
            requires = "middle/version"
        """)

    def setUp(self):
        client = TestClient()
        client.save({
            'top.py': self.top,
            'middle.py': self.middle,
            'app.py': self.app
        })
        client.run('create top.py top/version@')
        client.run('create middle.py middle/version@')
        self.cache_folder = client.cache_folder

    def test_pkg_config(self):
        t = TestClient(cache_folder=self.cache_folder)
        t.run('install middle/version@ -g pkg_config')
        content = t.load('middle.pc')
        self.assertIn('Requires: cmp1', content)


class WrongComponentsTestCase(unittest.TestCase):
    generators_using_components = ['pkg_config', 'CMakeDeps']

    top = textwrap.dedent("""
        from conans import ConanFile

        class Recipe(ConanFile):
            name = "top"

            def package_info(self):
                self.cpp_info.components["cmp1"].libs = ["top_cmp1"]
                self.cpp_info.components["cmp2"].libs = ["top_cmp2"]
    """)

    def test_unused_requirement(self):
        """ Requires should include all listed requirements
            This error is known when creating the package if the requirement is consumed.
        """
        consumer = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                requires = "top/version"
                def package_info(self):
                    self.cpp_info.requires = ["other::other"]
        """)
        t = TestClient()
        t.save({'top.py': self.top, 'consumer.py': consumer})
        t.run('create top.py top/version@')
        t.run('create consumer.py wrong/version@', assert_error=True)
        self.assertIn("wrong/version package_info(): Package require 'top' not used"
                      " in components requires", t.out)

    def test_wrong_requirement(self):
        """ If we require a wrong requirement, we get a meaninful error.
            This error is known when creating the package if the requirement is not there.
        """
        consumer = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                requires = "top/version"
                def package_info(self):
                    self.cpp_info.requires = ["top::cmp1", "other::other"]
        """)
        t = TestClient()
        t.save({'top.py': self.top, 'consumer.py': consumer})
        t.run('create top.py top/version@')
        t.run('create consumer.py wrong/version@', assert_error=True)
        self.assertIn("wrong/version package_info(): Package require 'other' declared in"
                      " components requires but not defined as a recipe requirement", t.out)
