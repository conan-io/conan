import unittest

from conan.test.utils.tools import TestClient


class BuildTypeSettingTest(unittest.TestCase):

    def test_build_type(self):
        # https://github.com/conan-io/conan/issues/2500
        client = TestClient()
        conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    settings = "build_type"
    def build(self):
        self.output.info("BUILD TYPE: %s" % (self.settings.build_type or "Not defined"))
"""
        test_conanfile = """from conan import ConanFile
class Pkg(ConanFile):
    settings = "build_type"
    def requirements(self):
        self.requires(self.tested_reference_str)
    def build(self):
        self.output.info("BUILD TYPE: %s" % (self.settings.build_type or "Not defined"))
    def test(self):
        pass
"""
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": ""})

        # This won't fail, as it has a build_type=None, which is allowed
        client.run("export . --name=pkg --version=0.1 --user=lasote --channel=testing")
        client.run("install --requires=pkg/0.1@lasote/testing -pr=myprofile --build='*'")
        self.assertEqual(1, str(client.out).count("BUILD TYPE: Not defined"))

        # test_package is totally consinstent with the regular package
        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing -pr=myprofile")
        self.assertEqual(2, str(client.out).count("BUILD TYPE: Not defined"))

        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": "[settings]\nbuild_type=Release"})

        client.run("export . --name=pkg --version=0.1 --user=user --channel=testing")
        client.run("install --requires=pkg/0.1@lasote/testing -pr=myprofile --build='*'")
        self.assertEqual(1, str(client.out).count("BUILD TYPE: Release"))

        client.run("create . --name=pkg --version=0.1 --user=lasote --channel=testing -pr=myprofile")
        self.assertEqual(2, str(client.out).count("BUILD TYPE: Release"))

        # Explicit build_tyep=None is NOT allowed, it is not a valid value
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test_conanfile,
                     "myprofile": "[settings]\nbuild_type=None"})

        client.run("export . --name=pkg --version=0.1 --user=lasote --channel=testing")
        client.run("install --requires=pkg/0.1@lasote/testing -pr=myprofile --build='*'",
                   assert_error=True)
        assert "ERROR: Invalid setting 'None' is not a valid 'settings.build_type'" in client.out
        assert "Possible values are ['Debug', 'Release', 'RelWithDebInfo', 'MinSizeRel']" in \
            client.out
