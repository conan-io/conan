import unittest
from conans.client.loader import ConanFileTextLoader, ConanFileLoader
from conans.errors import ConanException
from conans.util.files import save
import os
from conans.model.requires import Requirements
from conans.model.options import OptionsValues
from mock import Mock
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.model.scope import Scopes
from conans.model.profile import Profile
from collections import OrderedDict


class ConanLoaderTest(unittest.TestCase):

    def requires_init_test(self):
        loader = ConanFileLoader(None, Settings(), Profile())
        tmp_dir = temp_folder()
        conanfile_path = os.path.join(tmp_dir, "conanfile.py")
        conanfile = """from conans import ConanFile
class MyTest(ConanFile):
    requires = {}
    def requirements(self):
        self.requires("MyPkg/0.1@user/channel")
"""
        for requires in ("''", "[]", "()", "None"):
            save(conanfile_path, conanfile.format(requires))
            result = loader.load_conan(conanfile_path, output=None, consumer=True)
            result.requirements()
            self.assertEqual("MyPkg/0.1@user/channel", str(result.requires))

    def conanfile_txt_errors_test(self):
        # Valid content
        file_content = '''[requires}
OpenCV/2.4.10@phil/stable # My requirement for CV
'''
        with self.assertRaisesRegexp(ConanException, "Bad syntax"):
            ConanFileTextLoader(file_content)

        file_content = '{hello}'
        with self.assertRaisesRegexp(ConanException, "Unexpected line"):
            ConanFileTextLoader(file_content)

    def plain_text_parser_test(self):
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
        self.assertEquals(parser.requirements, exp)

    def load_conan_txt_test(self):
        file_content = '''[requires]
OpenCV/2.4.10@phil/stable
OpenCV2/2.4.10@phil/stable
[generators]
one
two
[imports]
OpenCV/bin, * -> ./bin # I need this binaries
OpenCV/lib, * -> ./lib
[options]
OpenCV:use_python=True
OpenCV:other_option=False
OpenCV2:use_python2=1
OpenCV2:other_option=Cosa
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, Settings(), Profile())
        ret = loader.load_conan_txt(file_path, None)
        options1 = OptionsValues.loads("""OpenCV:use_python=True
OpenCV:other_option=False
OpenCV2:use_python2=1
OpenCV2:other_option=Cosa""")
        requirements = Requirements()
        requirements.add("OpenCV/2.4.10@phil/stable")
        requirements.add("OpenCV2/2.4.10@phil/stable")

        self.assertEquals(ret.requires, requirements)
        self.assertEquals(ret.generators, ["one", "two"])
        self.assertEquals(ret.options.values.dumps(), options1.dumps())

        ret.copy = Mock()
        ret.imports()

        self.assertTrue(ret.copy.call_args_list, [('*', './bin', 'OpenCV/bin'),
                                                  ('*', './lib', 'OpenCV/lib')])

        # Now something that fails
        file_content = '''[requires]
OpenCV/2.4.104phil/stable
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, Settings(), Profile())
        with self.assertRaisesRegexp(ConanException, "Wrong package recipe reference(.*)"):
            loader.load_conan_txt(file_path, None)

        file_content = '''[requires]
OpenCV/2.4.10@phil/stable111111111111111111111111111111111111111111111111111111111111111
[imports]
OpenCV/bin/* - ./bin
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, Settings(), Profile())
        with self.assertRaisesRegexp(ConanException, "is too long. Valid names must contain"):
            loader.load_conan_txt(file_path, None)

    def test_package_settings(self):
        # CREATE A CONANFILE TO LOAD
        tmp_dir = temp_folder()
        conanfile_path = os.path.join(tmp_dir, "conanfile.py")
        conanfile = """from conans import ConanFile
class MyTest(ConanFile):
    requires = {}
    name = "MyPackage"
    version = "1.0"
    settings = "os"
"""
        save(conanfile_path, conanfile)

        # Apply windows for MyPackage
        profile = Profile()
        profile.package_settings = {"MyPackage": OrderedDict([("os", "Windows")])}
        loader = ConanFileLoader(None, Settings({"os": ["Windows", "Linux"]}), profile)

        recipe = loader.load_conan(conanfile_path, None)
        self.assertEquals(recipe.settings.os, "Windows")

        # Apply Linux for MyPackage
        profile.package_settings = {"MyPackage": OrderedDict([("os", "Linux")])}
        loader = ConanFileLoader(None, Settings({"os": ["Windows", "Linux"]}), profile)

        recipe = loader.load_conan(conanfile_path, None)
        self.assertEquals(recipe.settings.os, "Linux")

        # If the package name is different from the conanfile one, it wont apply
        profile.package_settings = {"OtherPACKAGE": OrderedDict([("os", "Linux")])}
        loader = ConanFileLoader(None, Settings({"os": ["Windows", "Linux"]}), profile)

        recipe = loader.load_conan(conanfile_path, None)
        self.assertIsNone(recipe.settings.os.value)
