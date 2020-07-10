import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ConanFileAssignmentTestCase(unittest.TestCase):
    """ Test that the value of the attribute 'provides' is properly assigned """

    def _check_provides_value(self, conanfile, expected):
        """ Provides assignment requires a fully built conanfile (with name) """
        t = TestClient()
        t.save({'conanfile.py': conanfile})
        t.run('export conanfile.py name/version@')
        t.run("info name/version@ --only provides --only url")
        self.assertIn("provides: {}".format(expected), t.out)

    def test_conanfile_explicit(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                url  = "the URL"
                provides = "provides_value"
        """)
        self._check_provides_value(conanfile, expected="provides_value")

    def test_conanfile_explicit_list(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                url  = "the URL"
                provides = ("liba", "libb")
        """)
        self._check_provides_value(conanfile, expected="liba, libb")

    def test_conanfile_from_name(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Recipe(ConanFile):
                name = "name"
                url  = "the URL"
        """)
        self._check_provides_value(conanfile, expected="name")
