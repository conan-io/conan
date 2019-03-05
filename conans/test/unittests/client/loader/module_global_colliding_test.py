# coding=utf-8

import os
import sys
import textwrap
import unittest

from parameterized import parameterized

from conans.client.loader import _parse_conanfile
from conans.client.tools.files import save, chdir
from conans.test.utils.test_files import temp_folder


class ModuleGlobalCollidingTest(unittest.TestCase):
    """ Scenario: Two conanfiles are using functionality from a package called 'fractions', one of
        them provides a `fractions.py` file with custom behavior while the other wants to
        use the system library.
    """

    def setUp(self):
        sys.modules.pop('fractions', None)
        self.assertFalse("fractions" in sys.modules.keys())

    @staticmethod
    def _create_module1():
        """ Module 1 provides its own implementation of 'fractions.Fraction' (returns float) """
        fractions = textwrap.dedent("""
            class Fraction:
               def __init__(self, num, den):
                   self._num = num
                   self._den = den

               def __str__(self):
                   return "{}".format(self._num/float(self._den))

        """)

        conanfile = textwrap.dedent("""
            from fractions import Fraction

            def get_fraction_str():
                return str(Fraction(1, 2))  # returns "0.5"
        """)

        tmp = temp_folder()
        with chdir(tmp):
            save("conanfile.py", conanfile)
            save("fractions.py", fractions)
            loaded, module_id = _parse_conanfile(os.path.join(tmp, "conanfile.py"))
        return loaded, module_id, "0.5"

    @staticmethod
    def _create_module2():
        """ Module 2 uses the built-in implementation (returns the fraction itself) """
        conanfile = textwrap.dedent("""
                    from fractions import Fraction

                    def get_fraction_str():
                        return str(Fraction(1, 2))  # returns "1/2"
                """)

        tmp = temp_folder()
        with chdir(tmp):
            save("conanfile.py", conanfile)
            loaded, module_id = _parse_conanfile(os.path.join(tmp, "conanfile.py"))
        return loaded, module_id, "1/2"

    def test_module1(self):
        """ Module 1 has its own implementation of the `fractions.Fraction` class """
        loaded, module_id, result = self._create_module1()
        self.assertEqual(loaded.get_fraction_str(), result)

    def test_module2(self):
        """ Module 2 uses the built-in 'fractions' module """
        loaded, module_id, result = self._create_module2()
        self.assertEqual(loaded.get_fraction_str(), result)

    @parameterized.expand([(True,), (False,)])
    def test_parse_order(self, inverse_load_order):
        """ The parse order of the conanfiles cannot affect the expected results """
        first, last = self._create_module1, self._create_module2
        if inverse_load_order:
            first, last = last, first

        loaded_first, _, result_first = first()
        loaded_last, _, result_last = last()

        self.assertNotEqual(result_first, result_last)
        self.assertEqual(loaded_first.get_fraction_str(), result_first)
        self.assertEqual(loaded_last.get_fraction_str(), result_last)

    def test_fail_for_custom(self):
        """ Module 1 has a custom implementation, but Conan already knows about the module """
        # Make module 'fractions' known to Conan itself.
        import fractions
        fractions
        self.assertTrue("fractions" in sys.modules.keys())

        loaded, module_id, result = self._create_module1()
        with self.assertRaisesRegexp(AssertionError, "1/2 != 0.5"):
            self.assertEqual(loaded.get_fraction_str(), result)
