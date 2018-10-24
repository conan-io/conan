import os
import tempfile
import unittest
import shutil
from parameterized import parameterized

from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.settings import Settings
from conans.test.utils.tools import TestClient
from conans.client.loader import ConanFileLoader
from conans.client.graph.python_requires import ConanPythonRequire
from conans.client.tools.files import save
from conans.client.tools.env import environment_append


class ConanFileTest(unittest.TestCase):
    def test_conanfile_naming(self):
        for member in vars(ConanFile):
            if member.startswith('_') and not member.startswith("__"):
                self.assertTrue(member.startswith('_conan'))

        conanfile = ConanFile(None, None)
        conanfile.initialize(Settings(), EnvValues())

        for member in vars(conanfile):
            if member.startswith('_') and not member.startswith("__"):
                self.assertTrue(member.startswith('_conan'))

    def test_conanfile_naming_complete(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    pass
    def package_info(self):
        for member in Pkg.__dict__:
            if member.startswith('_') and not member.startswith("__"):
                assert(member.startswith('_conan'))
        for member in vars(self):
            if member.startswith('_') and not member.startswith("__"):
                assert(member.startswith('_conan'))
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . PkgA/0.1@user/testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'PkgA/0.1@user/testing'")})
        client.run("create . PkgB/0.1@user/testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'PkgB/0.1@user/testing'")})
        client.run("create . PkgC/0.1@user/testing")


class ConanFileShortPathsTests(unittest.TestCase):
    conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    {short_paths}
    pass
    """

    def run(self, *args, **kwargs):
        tmp_folder = tempfile.mkdtemp(suffix='_conans')
        try:
            self.tmp_conanfile = os.path.join(tmp_folder, 'conanfile.py')
            super(ConanFileShortPathsTests, self).run(*args, **kwargs)
        finally:
            shutil.rmtree(tmp_folder, ignore_errors=True)

    def setUp(self):
        self.loader = ConanFileLoader(None, None, ConanPythonRequire(None, None))

    def test_default_behavior(self):
        save(self.tmp_conanfile, self.conanfile.format(short_paths=""))
        conanfile = self.loader.load_class(self.tmp_conanfile)

        self.assertEqual(False, conanfile.short_paths)

    @parameterized.expand([(False,), (True,)])
    def test_legacy_behaviour(self, short_paths):
        """ Assigning to ConanFile::short_paths will override the property itself """
        short_paths_str = "short_paths = True" if short_paths else "short_paths = False"
        save(self.tmp_conanfile, self.conanfile.format(short_paths=short_paths_str))
        conanfile = self.loader.load_class(self.tmp_conanfile)
        self.assertEqual(short_paths, conanfile.short_paths)

    @parameterized.expand([(False,), (True,)])
    def test_use_always_short_paths(self, short_paths):
        with environment_append({'CONAN_USE_ALWAYS_SHORT_PATHS': "True"}):
            short_paths_str = "_conan_short_paths = True" if short_paths else "_conan_short_paths = False"
            save(self.tmp_conanfile, self.conanfile.format(short_paths=short_paths_str))
            conanfile = self.loader.load_class(self.tmp_conanfile)
            self.assertEqual(True, conanfile.short_paths)

    @parameterized.expand([(False,), (True,)])
    def test_do_not_use_always_short_paths(self, short_paths):
        with environment_append({'CONAN_USE_ALWAYS_SHORT_PATHS': "False"}):
            short_paths_str = "_conan_short_paths = True" if short_paths else "_conan_short_paths = False"
            save(self.tmp_conanfile, self.conanfile.format(short_paths=short_paths_str))
            conanfile = self.loader.load_class(self.tmp_conanfile)
            self.assertEqual(short_paths, conanfile.short_paths)
