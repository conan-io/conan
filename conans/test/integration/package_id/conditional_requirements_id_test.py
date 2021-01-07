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
            self.requires("optional/0.1@user/testing")
    def package_id(self):
        if self.options.use_lib:
            self.info.requires.remove("optional")
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . pkgA/0.1@user/testing")
        self.assertIn(NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("create . pkgA/0.1@user/testing -o pkgA:use_lib=True")
        self.assertIn("b3485d1af719b8ddc636d57800186fc73cefff8d", client.out)
        conanfile = '''from conans import ConanFile
class ConanLib(ConanFile):
    requires = "pkgA/0.1@user/testing"
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . pkgB/0.1@user/testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:4778d500bd98ecb57d331d591aa43a7b4788d870", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgB")})
        client.run("create . pkgC/0.1@user/testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:4778d500bd98ecb57d331d591aa43a7b4788d870", client.out)
        self.assertIn("pkgC/0.1@user/testing:4866ff85840783bec107794cce1bc12b7b8df188", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgC")})
        client.run("install .")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:4778d500bd98ecb57d331d591aa43a7b4788d870", client.out)
        self.assertIn("pkgC/0.1@user/testing:4866ff85840783bec107794cce1bc12b7b8df188", client.out)

        client.run("install . -o pkgA:use_lib=True")
        self.assertIn("pkgA/0.1@user/testing:b3485d1af719b8ddc636d57800186fc73cefff8d", client.out)
        self.assertIn("pkgB/0.1@user/testing:4778d500bd98ecb57d331d591aa43a7b4788d870", client.out)
        self.assertIn("pkgC/0.1@user/testing:4866ff85840783bec107794cce1bc12b7b8df188", client.out)
