# coding=utf-8

import os
import sys
import textwrap
import unittest

from parameterized import parameterized

from conans.client.hook_manager import HookManager
from conans.client.tools.files import chdir
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class ModuleGlobalCollidingTest(unittest.TestCase):
    """ Scenario: Two hooks are using functionality from a package called 'fractions', one of
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

        hook = textwrap.dedent("""
            from fractions import Fraction

            def pre_export(output, *args, **kwargs):
                value = str(Fraction(1, 2))  # returns "0.5"
                output.info(">>>> {}".format(value))
        """)

        tmp = temp_folder()
        with chdir(tmp):
            save("hook.py", hook)
            save("fractions.py", fractions)

        return os.path.join(tmp, "hook"), "0.5"

    @staticmethod
    def _create_module2():
        """ Module 2 uses the built-in implementation (returns the fraction itself) """
        hook = textwrap.dedent("""
            from fractions import Fraction

            def pre_export(output, *args, **kwargs):
                value = str(Fraction(1, 2))  # returns "1/2"
                output.info(">>>> {}".format(value))
        """)

        tmp = temp_folder()
        with chdir(tmp):
            save("hook.py", hook)
        return os.path.join(tmp, "hook"), "1/2"

    def test_hook1(self):
        """ Module 1 has its own implementation of the `fractions.Fraction` class """
        hook, ret = self._create_module1()

        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_folder(), [hook, ], output)
        hook_manager.load_hooks()
        hook_manager.execute("pre_export")
        print(output)
        self.assertIn(">>>> {}".format(ret), output)

    def test_hook2(self):
        """ Module 2 uses the built-in 'fractions' module """
        hook, ret = self._create_module2()

        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_folder(), [hook, ], output)
        hook_manager.load_hooks()
        hook_manager.execute("pre_export")

        self.assertIn(">>>> {}".format(ret), output)

    @parameterized.expand([(True,), (False,)])
    def test_parse_order(self, inverse_load_order):
        """ The parse order of the conanfiles cannot affect the expected results """
        first, last = self._create_module1, self._create_module2
        if inverse_load_order:
            first, last = last, first

        hook_first, result_first = first()
        hook_last, result_last = last()

        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_folder(), [hook_first, hook_last ], output)
        hook_manager.load_hooks()
        hook_manager.execute("pre_export")

        self.assertIn(">>>> {}".format(result_first), output)
        self.assertIn(">>>> {}".format(result_last), output)

    def test_fail_for_custom(self):
        """ Module 1 has a custom implementation, but Conan already knows about the module """
        # Make module 'fractions' known to Conan itself.
        import fractions
        fractions
        self.assertTrue("fractions" in sys.modules.keys())

        hook, result = self._create_module1()
        with self.assertRaisesRegexp(AssertionError, ">>>> 0.5"):
            output = TestBufferConanOutput()
            hook_manager = HookManager(temp_folder(), [hook, ], output)
            hook_manager.load_hooks()
            hook_manager.execute("pre_export")

            self.assertIn(">>>> {}".format(result), output)
