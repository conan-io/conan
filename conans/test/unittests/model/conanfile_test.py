import unittest

from conans.model.conan_file import ConanFile
from conans.model.settings import Settings
from conans.test.utils.tools import TestClient


class ConanFileTest(unittest.TestCase):
    def test_conanfile_naming(self):
        for member in vars(ConanFile):
            if member.startswith('_') and not member.startswith("__"):
                self.assertTrue(member.startswith('_conan'))

        conanfile = ConanFile(None)

        for member in vars(conanfile):
            if member.startswith('_') and not member.startswith("__"):
                self.assertTrue(member.startswith('_conan'))

    def test_conanfile_naming_complete(self):
        client = TestClient()
        conanfile = """from conan import ConanFile
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
        client.run("create . --name=pkga --version=0.1 --user=user --channel=testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'pkga/0.1@user/testing'")})
        client.run("create . --name=pkgb --version=0.1 --user=user --channel=testing")
        client.save({"conanfile.py": conanfile.replace("pass",
                                                       "requires = 'pkgb/0.1@user/testing'")})
        client.run("create . --name=pkgc --version=0.1 --user=user --channel=testing")
