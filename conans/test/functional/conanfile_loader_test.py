import unittest
from conans.client.loader import ConanFileTextLoader, ConanFileLoader,\
    ProcessedProfile
from conans.errors import ConanException
from conans.util.files import save
import os
from conans.model.requires import Requirements
from conans.model.options import OptionsValues
from mock import Mock
from conans.model.settings import Settings
from conans.test.utils.test_files import temp_folder
from conans.model.profile import Profile
from collections import OrderedDict
from mock.mock import call
from conans.client.graph.python_requires import ConanPythonRequire


class ConanLoaderTest(unittest.TestCase):

    def inherit_short_paths_test(self):
        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
        tmp_dir = temp_folder()
        conanfile_path = os.path.join(tmp_dir, "conanfile.py")
        conanfile = """from base_recipe import BasePackage
class Pkg(BasePackage):
    pass
"""
        base_recipe = """from conans import ConanFile
class BasePackage(ConanFile):
    short_paths = True
"""
        save(conanfile_path, conanfile)
        save(os.path.join(tmp_dir, "base_recipe.py"), base_recipe)
        conan_file = loader.load_class(conanfile_path)
        self.assertEqual(conan_file.short_paths, True)

        result = loader.load_conanfile(conanfile_path, output=None, consumer=True,
                                       processed_profile=ProcessedProfile())
        self.assertEqual(result.short_paths, True)

    def requires_init_test(self):
        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))
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
            result = loader.load_conanfile(conanfile_path, output=None, consumer=True,
                                           processed_profile=ProcessedProfile())
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

        file_content = '[imports]\nhello'
        with self.assertRaisesRegexp(ConanException, "Invalid imports line: hello"):
            ConanFileTextLoader(file_content).imports_method(None)

        file_content = '[imports]\nbin, * -> bin @ kk=3 '
        with self.assertRaisesRegexp(ConanException, "Unknown argument kk"):
            ConanFileTextLoader(file_content).imports_method(None)

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
[build_requires]
MyPkg/1.0.0@phil/stable
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
        loader = ConanFileLoader(None, None, None)
        ret = loader.load_conanfile_txt(file_path, None, ProcessedProfile())
        options1 = OptionsValues.loads("""OpenCV:use_python=True
OpenCV:other_option=False
OpenCV2:use_python2=1
OpenCV2:other_option=Cosa""")
        requirements = Requirements()
        requirements.add("OpenCV/2.4.10@phil/stable")
        requirements.add("OpenCV2/2.4.10@phil/stable")
        build_requirements = []
        build_requirements.append("MyPkg/1.0.0@phil/stable")

        self.assertEquals(ret.requires, requirements)
        self.assertEquals(ret.build_requires, build_requirements)
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
        loader = ConanFileLoader(None, None, None)
        with self.assertRaisesRegexp(ConanException, "Wrong package recipe reference(.*)"):
            loader.load_conanfile_txt(file_path, None, ProcessedProfile())

        file_content = '''[requires]
OpenCV/2.4.10@phil/stable111111111111111111111111111111111111111111111111111111111111111
[imports]
OpenCV/bin/* - ./bin
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, None, None)
        with self.assertRaisesRegexp(ConanException, "is too long. Valid names must contain"):
            loader.load_conanfile_txt(file_path, None, ProcessedProfile())

    def load_imports_arguments_test(self):
        file_content = '''
[imports]
OpenCV/bin, * -> ./bin # I need this binaries
OpenCV/lib, * -> ./lib @ root_package=Pkg
OpenCV/data, * -> ./data @ root_package=Pkg, folder=True # Irrelevant
docs, * -> ./docs @ root_package=Pkg, folder=True, ignore_case=True, excludes="a b c" # Other
licenses, * -> ./licenses @ root_package=Pkg, folder=True, ignore_case=True, excludes="a b c", keep_path=False # Other
'''
        tmp_dir = temp_folder()
        file_path = os.path.join(tmp_dir, "file.txt")
        save(file_path, file_content)
        loader = ConanFileLoader(None, None, None)
        ret = loader.load_conanfile_txt(file_path, None, ProcessedProfile())

        ret.copy = Mock()
        ret.imports()
        expected = [call(u'*', u'./bin', u'OpenCV/bin', None, False, False, None, True),
                    call(u'*', u'./lib', u'OpenCV/lib', u'Pkg', False, False, None, True),
                    call(u'*', u'./data', u'OpenCV/data', u'Pkg', True, False, None, True),
                    call(u'*', u'./docs', u'docs', u'Pkg', True, True, [u'"a', u'b', u'c"'], True),
                    call(u'*', u'./licenses', u'licenses', u'Pkg', True, True, [u'"a', u'b', u'c"'],
                         False)]
        self.assertEqual(ret.copy.call_args_list, expected)

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
        loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))

        recipe = loader.load_conanfile(conanfile_path, None,
                                       ProcessedProfile(Settings({"os": ["Windows", "Linux"]}), profile))
        self.assertEquals(recipe.settings.os, "Windows")

        # Apply Linux for MyPackage
        profile.package_settings = {"MyPackage": OrderedDict([("os", "Linux")])}
        recipe = loader.load_conanfile(conanfile_path, None,
                                       ProcessedProfile(Settings({"os": ["Windows", "Linux"]}), profile))
        self.assertEquals(recipe.settings.os, "Linux")

        # If the package name is different from the conanfile one, it wont apply
        profile.package_settings = {"OtherPACKAGE": OrderedDict([("os", "Linux")])}
        recipe = loader.load_conanfile(conanfile_path, None,
                                       ProcessedProfile(Settings({"os": ["Windows", "Linux"]}), profile))
        self.assertIsNone(recipe.settings.os.value)
