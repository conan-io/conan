import unittest
from conans.test.utils.tools import TestClient


class BuildTypeSettingTest(unittest.TestCase):

    def test_build_type(self):
        # https://github.com/conan-io/conan/issues/2500
        client = TestClient()
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "build_type"
    def build(self):
        self.output.info("BUILD TYPE: %s" % (self.settings.build_type or "Not defined"))
"""
        test_conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    settings = "build_type"
    def build(self):
        self.output.info("BUILD TYPE: %s" % (self.settings.build_type or "Not defined"))
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": ""})

        # This won't fail, as it has a build_type=None, which is allowed
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -pr=myprofile --build")
        self.assertEqual(1, str(client.out).count("BUILD TYPE: Not defined"))

        # This is an error. test_package/conanfile won't have build_type defined, more restrictive
        error = client.run("create . Pkg/0.1@lasote/testing -pr=myprofile", ignore_error=True)
        self.assertTrue(error)
        self.assertEqual(1, str(client.out).count("BUILD TYPE: Not defined"))
        self.assertIn("ConanException: 'settings.build_type' doesn't exist", client.out)

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": "[settings]\nbuild_type=None"})

        # This won't fail, as it has a build_type=None, which is allowed
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("install Pkg/0.1@lasote/testing -pr=myprofile --build")
        self.assertEqual(1, str(client.out).count("BUILD TYPE: Not defined"))

        # This is NOT an error. build_type has a value = None
        client.run("create . Pkg/0.1@lasote/testing -pr=myprofile")
        self.assertEqual(2, str(client.out).count("BUILD TYPE: Not defined"))
