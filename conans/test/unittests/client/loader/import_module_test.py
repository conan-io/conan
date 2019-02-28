# coding=utf-8

import os
import textwrap
import unittest

import six
from parameterized import parameterized

from conans.client.loader import _parse_conanfile
from conans.client.tools.files import save, chdir
from conans.errors import ConanException
from conans.test.utils.test_files import temp_folder


class ImportModuleLoaderTest(unittest.TestCase):

    @staticmethod
    def _create_and_load(myfunc, value, subdir_name, add_subdir_init):
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

        conanfile = textwrap.dedent("""
            from {subdir}.api import get_value, {myfunc}
            from file import get_side_value, side_{myfunc}
            from fractions import Fraction

            def conanfile_func():
                return get_value(), {myfunc}(), get_side_value(), side_{myfunc}(), str(Fraction(1,1))
        """)
        expected_return = (value, myfunc, value, myfunc, "1")

        tmp = temp_folder()
        with chdir(tmp):
            save("conanfile.py", conanfile.format(value=value, myfunc=myfunc, subdir=subdir_name))
            save("file.py", side_content.format(value=value, myfunc=myfunc))
            save("{}/api.py".format(subdir_name), subdir_content.format(value=value, myfunc=myfunc))
            if add_subdir_init:
                save("{}/__init__.py".format(subdir_name), "")

        loaded, module_id = _parse_conanfile(os.path.join(tmp, "conanfile.py"))
        return loaded, module_id, expected_return

    @unittest.skipIf(six.PY2, "Python 2 requires __init__.py file in modules")
    def test_py3_recipe_colliding_filenames(self):
        myfunc1, value1 = "recipe1", 42
        myfunc2, value2 = "recipe2", 23
        loaded1, module_id1, exp_ret1 = self._create_and_load(myfunc1, value1, "subdir", False)
        loaded2, module_id2, exp_ret2 = self._create_and_load(myfunc2, value2, "subdir", False)

        self.assertNotEqual(module_id1, module_id2)
        self.assertEqual(loaded1.conanfile_func(), exp_ret1)
        self.assertEqual(loaded2.conanfile_func(), exp_ret2)

    def test_recipe_colliding_filenames(self):
        myfunc1, value1 = "recipe1", 42
        myfunc2, value2 = "recipe2", 23
        loaded1, module_id1, exp_ret1 = self._create_and_load(myfunc1, value1, "subdir", True)
        loaded2, module_id2, exp_ret2 = self._create_and_load(myfunc2, value2, "subdir", True)

        self.assertNotEqual(module_id1, module_id2)
        self.assertEqual(loaded1.conanfile_func(), exp_ret1)
        self.assertEqual(loaded2.conanfile_func(), exp_ret2)

    @parameterized.expand([(True, ), (False, )])
    def test_wrong_imports(self, add_subdir_init):
        myfunc1, value1 = "recipe1", 42

        # Item imported does not exist, but file exists
        with self.assertRaisesRegexp(ConanException, "Unable to load conanfile in"):
            self._create_and_load(myfunc1, value1, "requests", add_subdir_init)

        # File does not exists in already existing module
        with self.assertRaisesRegexp(ConanException, "Unable to load conanfile in"):
            self._create_and_load(myfunc1, value1, "conans", add_subdir_init)
