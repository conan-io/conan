import unittest
from conans.model.conan_file import ConanFile
from conans.model.env_info import EnvValues
from conans.model.settings import Settings
from conans.test.utils.tools import TestClient


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
