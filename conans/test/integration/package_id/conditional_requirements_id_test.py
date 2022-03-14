import unittest

import pytest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient


class ConditionalRequirementsIdTest(unittest.TestCase):

    @pytest.mark.xfail(reason="Now dependencies are transitive for package id by default")
    def test_basic(self):
        # https://github.com/conan-io/conan/issues/3792
        # Default might be improved 2.0 in https://github.com/conan-io/conan/issues/3762
        client = TestClient()
        client.save({"conanfile.py": GenConanfile()})
        client.run("create . --name=optional --version=0.1 --user=user --channel=testing")
        conanfile = '''from conan import ConanFile
class ConanLib(ConanFile):
    options = {"use_lib": [True, False]}
    default_options= {"use_lib": False}
    def requirements(self):
        if self.options.use_lib:
            self.requires("optional/0.1@user/testing", public=False)
    def package_id(self):
        if self.options.use_lib:
            self.info.requires.remove("optional")
'''
        client.save({"conanfile.py": conanfile})
        client.run("create . --name=pkgA --version=0.1 --user=user --channel=testing")
        self.assertIn(NO_SETTINGS_PACKAGE_ID, client.out)
        client.run("create . --name=pkgA --version=0.1 --user=user --channel=testing -o pkgA/*:use_lib=True")
        self.assertIn("9824b101f894df7e2b106af5055272fc083f3008", client.out)

        client.save({"conanfile.py": GenConanfile().with_requires("pkgA/0.1@user/testing")})
        client.run("create . --name=pkgB --version=0.1 --user=user --channel=testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:6d027ca5b485c4bb8d95034b659613b57e5192d6", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgB")})
        client.run("create . --name=pkgC --version=0.1 --user=user --channel=testing")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:6d027ca5b485c4bb8d95034b659613b57e5192d6", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)

        client.save({"conanfile.py": conanfile.replace("pkgA", "pkgC")})
        client.run("install .")
        self.assertIn("pkgA/0.1@user/testing:%s" % NO_SETTINGS_PACKAGE_ID, client.out)
        self.assertIn("pkgB/0.1@user/testing:6d027ca5b485c4bb8d95034b659613b57e5192d6", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)

        client.run("install . -o pkgA:use_lib=True")
        self.assertIn("pkgA/0.1@user/testing:30b83bef2eb3dc4ba0692e15c29f09c5953a7735", client.out)
        self.assertIn("pkgB/0.1@user/testing:6d027ca5b485c4bb8d95034b659613b57e5192d6", client.out)
        self.assertIn("pkgC/0.1@user/testing:51ac26b3b7f3497f8e15e77491c4d1fcc8bb58dd", client.out)
