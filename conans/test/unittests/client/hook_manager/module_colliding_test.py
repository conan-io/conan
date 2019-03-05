# coding=utf-8

import os
import textwrap
import unittest

import six

from conans.client.hook_manager import HookManager
from conans.client.tools.files import chdir
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestBufferConanOutput
from conans.util.files import save


class ModuleCollidingTest(unittest.TestCase):
    """ Scenario: there are two hooks that are accompanied by files with the same name. As
        hooks are loaded dynamically (and doesn't know about each other), each of them
        should use the functions in the files that are in its same folder/package.
    """

    @staticmethod
    def _create(myfunc, value, subdir_name, add_subdir_init):
        subdir_content = textwrap.dedent("""
            def get_value():
                return {value}

            def {myfunc}():
                return "{myfunc}"
        """)

        side_content = textwrap.dedent("""
            def get_side_value():
                return {value}

            def side_{myfunc}():
                return "{myfunc}"
        """)

        hook = textwrap.dedent("""
            from {subdir}.api import get_value, {myfunc}
            from file import get_side_value, side_{myfunc}
            from fractions import Fraction

            def pre_export(output, *args, **kwargs):
                output.info(">{myfunc}< get_value(): {{}}".format(get_value()))
                output.info(">{myfunc}< {myfunc}(): {{}}".format({myfunc}()))
                output.info(">{myfunc}< get_side_value(): {{}}".format(get_side_value()))
                output.info(">{myfunc}< side_{myfunc}(): {{}}".format(side_{myfunc}()))
                
        """)
        expected_return = (("get_value()", value),
                           ("{}()".format(myfunc), myfunc),
                           ("get_side_value()", value),
                           ("side_{}()".format(myfunc), myfunc))

        tmp = temp_folder()
        with chdir(tmp):
            save("hook.py", hook.format(value=value, myfunc=myfunc, subdir=subdir_name))
            save("file.py", side_content.format(value=value, myfunc=myfunc))
            save("{}/api.py".format(subdir_name), subdir_content.format(value=value, myfunc=myfunc))
            if add_subdir_init:
                save("{}/__init__.py".format(subdir_name), "")

        return os.path.join(tmp, "hook"), expected_return

    @unittest.skipIf(six.PY2, "Python 2 requires __init__.py file in modules")
    def test_py3_recipe_colliding_filenames(self):
        myfunc1, value1 = "recipe1", 42
        myfunc2, value2 = "recipe2", 23
        hook1, exp_ret1 = self._create(myfunc1, value1, "subdir", False)
        hook2, exp_ret2 = self._create(myfunc2, value2, "subdir", False)

        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_folder(), [hook1, hook2], output)
        hook_manager.load_hooks()
        hook_manager.execute("pre_export")

        # Outputs from hook1:
        for item, value in exp_ret1:
            self.assertIn(">{}< {}: {}".format(myfunc1, item, value), output)

        # Outputs from hook2:
        for item, value in exp_ret2:
            self.assertIn(">{}< {}: {}".format(myfunc2, item, value), output)

    def test_recipe_colliding_filenames(self):
        myfunc1, value1 = "recipe1", 42
        myfunc2, value2 = "recipe2", 23
        hook1, exp_ret1 = self._create(myfunc1, value1, "subdir", True)
        hook2, exp_ret2 = self._create(myfunc2, value2, "subdir", True)

        output = TestBufferConanOutput()
        hook_manager = HookManager(temp_folder(), [hook1, hook2], output)
        hook_manager.load_hooks()
        hook_manager.execute("pre_export")

        # Outputs from hook1:
        for item, value in exp_ret1:
            self.assertIn(">{}< {}: {}".format(myfunc1, item, value), output)

        # Outputs from hook2:
        for item, value in exp_ret2:
            self.assertIn(">{}< {}: {}".format(myfunc2, item, value), output)

    def test_wrong_imports(self):
        myfunc1, value1 = "recipe1", 42

        # Item imported does not exist, but file exists
        with self.assertRaisesRegexp(ConanException, "Error loading hook"):
            hook1, exp_ret1 = self._create(myfunc1, value1, "requests", True)
            output = TestBufferConanOutput()
            hook_manager = HookManager(temp_folder(), [hook1,], output)
            hook_manager.load_hooks()

        # File does not exists in already existing module
        with self.assertRaisesRegexp(ConanException, "Error loading hook"):
            hook1, exp_ret1 = self._create(myfunc1, value1, "conans", True)
            output = TestBufferConanOutput()
            hook_manager = HookManager(temp_folder(), [hook1, ], output)
            hook_manager.load_hooks()
