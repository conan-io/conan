import unittest

import pytest

from conans.test.utils.tools import TestClient


@pytest.mark.xfail(reason="the dependencies options effect will be via package_id and requires")
class TransitiveOptionsAffectPackageIDTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        conanfile = '''from conans import ConanFile
class Pkg(ConanFile):
    options = {"shared": [True, False], "num": [1, 2, 3]}
    default_options= {"shared": False, "num": 1}
'''

        client.save({"conanfile.py": conanfile})
        client.run("create . pkga/0.1@user/testing")
        self.assertIn("e522a4e1c101d2a2b4f0009497ae0d0b6a29ae65", client.out)
        client.run("create . pkga/0.1@user/testing -o pkga:shared=True -o pkga:num=2")
        self.assertIn("18d072f161b7c8d77083ca6dec0c5222f4bacf22", client.out)
        client.save({"conanfile.py": conanfile + "    requires = 'pkga/0.1@user/testing'"})
        client.run("create . pkgb/0.1@user/testing")
        client.save({"conanfile.py": conanfile + "    requires = 'pkgb/0.1@user/testing'"})
        client.run("create . PkgC/0.1@user/testing")
        client.save({"conanfile.py": conanfile + "    requires = 'PkgC/0.1@user/testing'"})

        client.run("install .")
        self.assertIn("pkga/0.1@user/testing:e522a4e1c101d2a2b4f0009497ae0d0b6a29ae65", client.out)
        self.assertIn("pkgb/0.1@user/testing:fba7313915d1eaaa52c0a64d2f576c62e2cabd5d", client.out)
        self.assertIn("PkgC/0.1@user/testing:95cf05dd9309c4c4f3c5d8a881ff13d93481974e", client.out)
        client.run("install . -o pkga:shared=True -o pkga:num=2")
        # Only PkgA changes!
        self.assertIn("pkga/0.1@user/testing:18d072f161b7c8d77083ca6dec0c5222f4bacf22", client.out)
        self.assertIn("pkgb/0.1@user/testing:fba7313915d1eaaa52c0a64d2f576c62e2cabd5d", client.out)
        self.assertIn("PkgC/0.1@user/testing:95cf05dd9309c4c4f3c5d8a881ff13d93481974e", client.out)
