import os
import sys
import textwrap
import unittest

import pytest
from parameterized import parameterized

from conans.client.loader import ConanFileLoader, ConanFileTextLoader, load_python_file
from conans.errors import ConanException
from conan.test.utils.test_files import temp_folder
from conans.util.files import save, chdir


class ConanLoaderTest(unittest.TestCase):

    def test_inherit_short_paths(self):
        loader = ConanFileLoader(None)

        tmp_dir = temp_folder()
        conanfile_path = os.path.join(tmp_dir, "conanfile.py")
        conanfile = """from base_recipe import BasePackage
class Pkg(BasePackage):
    pass
"""
        base_recipe = """from conan import ConanFile
class BasePackage(ConanFile):
    short_paths = True
"""
        save(conanfile_path, conanfile)
        save(os.path.join(tmp_dir, "base_recipe.py"), base_recipe)
        conan_file = loader.load_basic(conanfile_path)
        self.assertEqual(conan_file.short_paths, True)

        result = loader.load_consumer(conanfile_path)
        self.assertEqual(result.short_paths, True)


class ConanLoaderTxtTest(unittest.TestCase):
    def test_conanfile_txt_errors(self):
        # Invalid content
        file_content = '''[requires}
OpenCV/2.4.10@phil/stable # My requirement for CV
'''
        with self.assertRaisesRegex(ConanException, "Bad syntax"):
            ConanFileTextLoader(file_content)

        file_content = '{hello}'
        with self.assertRaisesRegex(ConanException, "Unexpected line"):
            ConanFileTextLoader(file_content)

    def test_plain_text_parser(self):
        # Valid content
        file_content = '''[requires]
OpenCV/2.4.10@phil/stable # My requirement for CV
OpenCV2/2.4.10@phil/stable #
OpenCV3/2.4.10@phil/stable
[generators]
one # My generator for this
two
[options]
OpenCV:use_python=True # Some option
OpenCV:other_option=False
OpenCV2:use_python2=1
OpenCV2:other_option=Cosa #
'''
        parser = ConanFileTextLoader(file_content)
        exp = ['OpenCV/2.4.10@phil/stable',
               'OpenCV2/2.4.10@phil/stable',
               'OpenCV3/2.4.10@phil/stable']
        self.assertEqual(parser.requirements, exp)

    def test_revision_parsing(self):
        # Valid content
        file_content = '''[requires]
OpenCV/2.4.10@user/stable#RREV1 # My requirement for CV
'''
        parser = ConanFileTextLoader(file_content)
        exp = ['OpenCV/2.4.10@user/stable#RREV1']
        self.assertEqual(parser.requirements, exp)

    def test_load_conan_txt(self):
        file_content = '''[requires]
OpenCV/2.4.10@phil/stable
OpenCV2/2.4.10@phil/stable
[tool_requires]
Mypkg/1.0.0@phil/stable
[generators]
one
two
[options]
OpenCV/*:use_python=True
OpenCV/*:other_option=False
OpenCV2/*:use_python2=1
OpenCV2/*:other_option=Cosa
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, None)
        ret = loader.load_conanfile_txt(file_path)

        self.assertEqual(len(ret.requires.values()), 3)
        self.assertEqual(ret.generators, ["one", "two"])
        self.assertEqual(ret.options.dumps(), 'OpenCV/*:other_option=False\n'
                                              'OpenCV/*:use_python=True\n'
                                              'OpenCV2/*:other_option=Cosa\n'
                                              'OpenCV2/*:use_python2=1')

    def test_load_options_error(self):
        conanfile_txt = textwrap.dedent("""
            [options]
            myoption: myvalue
        """)
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, conanfile_txt)
        loader = ConanFileLoader(None, None)
        with self.assertRaisesRegex(ConanException,
                                    r"Error while parsing \[options\] in conanfile.txt\n"
                                    r"Options should be specified as 'pkg/\*:option=value'"):
            loader.load_conanfile_txt(file_path)

    def test_layout_not_predefined(self):
        txt = textwrap.dedent("""
                    [layout]
                    missing
                """)
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.txt")
        save(file_path, txt)
        with pytest.raises(ConanException) as exc:
            loader = ConanFileLoader(None, None)
            loader.load_conanfile_txt(file_path)
        assert "Unknown predefined layout 'missing'" in str(exc.value)

    def test_layout_multiple(self):
        txt = textwrap.dedent("""
                    [layout]
                    cmake_layout
                    vs_layout
                """)
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "conanfile.txt")
        save(file_path, txt)
        with pytest.raises(ConanException) as exc:
            loader = ConanFileLoader(None, None)
            loader.load_conanfile_txt(file_path)
        assert "Only one layout can be declared in the [layout] section of the conanfile.txt" \
               in str(exc.value)


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
            import pickle
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
                save("__init__.py", "")
                save("{}/__init__.py".format(subdir_name), "")

        loaded, module_id = load_python_file(os.path.join(tmp, "conanfile.py"))
        return loaded, module_id, expected_return

    @parameterized.expand([(True, False), (False, True), (False, False)])
    def test_py3_recipe_colliding_init_filenames(self, sub1, sub2):
        myfunc1, value1 = "recipe1", 42
        myfunc2, value2 = "recipe2", 23
        loaded1, module_id1, exp_ret1 = self._create_and_load(myfunc1, value1, "subdir", sub1)
        loaded2, module_id2, exp_ret2 = self._create_and_load(myfunc2, value2, "subdir", sub2)

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
        # We use some existing and imported Python stdlib import
        with self.assertRaisesRegex(ConanException, "Unable to load conanfile in"):
            self._create_and_load(myfunc1, value1, "textwrap", add_subdir_init)

        # File does not exists in already existing module
        with self.assertRaisesRegex(ConanException, "Unable to load conanfile in"):
            self._create_and_load(myfunc1, value1, "conans", add_subdir_init)

    def test_helpers_python_library(self):
        mylogger = """
value = ""
def append(data):
    global value
    value += data
"""
        temp = temp_folder()
        save(os.path.join(temp, "myconanlogger.py"), mylogger)

        conanfile = "import myconanlogger"
        temp1 = temp_folder()
        save(os.path.join(temp1, "conanfile.py"), conanfile)
        temp2 = temp_folder()
        save(os.path.join(temp2, "conanfile.py"), conanfile)

        try:
            sys.path.append(temp)
            loaded1, _ = load_python_file(os.path.join(temp1, "conanfile.py"))
            loaded2, _ = load_python_file(os.path.join(temp2, "conanfile.py"))
            self.assertIs(loaded1.myconanlogger, loaded2.myconanlogger)
            self.assertIs(loaded1.myconanlogger.value, loaded2.myconanlogger.value)
        finally:
            sys.path.remove(temp)
