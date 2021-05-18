import unittest

from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


class ConditionalRequirementsIdTest(unittest.TestCase):

    def test_basic(self):
        # https://github.com/conan-io/conan/issues/3792
        # Default might be improved 2.0 in https://github.com/conan-io/conan/issues/3762
        client = TestClient()
        conanfile = '''from conans import ConanFile
class ConanLib(ConanFile):
    pass
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . optional/0.1@user/testing")
        conanfile = '''from conans import ConanFile
class ConanLib(ConanFile):
    options = {"use_lib": [True, False]}
    default_options= "use_lib=False"
    def requirements(self):
        if self.options.use_lib:
            self.requires("optional/0.1@user/testing", public=False)
    def package_id(self):
        if self.options.use_lib:
            self.info.requires.remove("optional")
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . pkgA/0.1@user/testing")
        self.assertIn(NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("create . pkgA/0.1@user/testing -o pkgA:use_lib=True")
        self.assertIn("30b83bef2eb3dc4ba0692e15c29f09c5953a7735", client.out)
        conanfile = '''from conans import ConanFile
class ConanLib(ConanFile):
    requires = "pkgA/0.1@user/testing"
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . pkgB/0.1@user/testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:5858e6dc7a216040dfdccc8eb00e80711e56f5ea", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgB")})
        client.run("create . pkgC/0.1@user/testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:5858e6dc7a216040dfdccc8eb00e80711e56f5ea", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgC")})
        client.run("install .")
        print(client.out)
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:5858e6dc7a216040dfdccc8eb00e80711e56f5ea", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)

        client.run("install . -o pkgA:use_lib=True")
        self.assertIn("pkgA/0.1@user/testing:30b83bef2eb3dc4ba0692e15c29f09c5953a7735", client.out)
        self.assertIn("pkgB/0.1@user/testing:5858e6dc7a216040dfdccc8eb00e80711e56f5ea", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)
