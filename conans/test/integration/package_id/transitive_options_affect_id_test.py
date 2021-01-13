import unittest

from conans.test.utils.tools import TestClient


class TransitiveOptionsAffectPackageIDTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        conanfile = '''from conans import ConanFile
class Pkg(ConanFile):
    options = {"shared": [True, False], "num": [1, 2, 3]}
    default_options= "shared=False", "num=1"
'''

        client.save({"conanfile.py": conanfile})
        client.run("create . PkgA/0.1@user/testing")
        self.assertIn("e522a4e1c101d2a2b4f0009497ae0d0b6a29ae65", client.out)
        client.run("create . PkgA/0.1@user/testing -o PkgA:shared=True -o PkgA:num=2")
        self.assertIn("18d072f161b7c8d77083ca6dec0c5222f4bacf22", client.out)
        client.save({"conanfile.py": conanfile + "    requires = 'PkgA/0.1@user/testing'"})
        client.run("create . PkgB/0.1@user/testing")
        client.save({"conanfile.py": conanfile + "    requires = 'PkgB/0.1@user/testing'"})
        client.run("create . PkgC/0.1@user/testing")
        client.save({"conanfile.py": conanfile + "    requires = 'PkgC/0.1@user/testing'"})

        client.run("install .")
        self.assertIn("PkgA/0.1@user/testing:e522a4e1c101d2a2b4f0009497ae0d0b6a29ae65", client.out)
        self.assertIn("PkgB/0.1@user/testing:fba7313915d1eaaa52c0a64d2f576c62e2cabd5d", client.out)
        self.assertIn("PkgC/0.1@user/testing:95cf05dd9309c4c4f3c5d8a881ff13d93481974e", client.out)
        client.run("install . -o PkgA:shared=True -o PkgA:num=2")
        # Only PkgA changes!
        self.assertIn("PkgA/0.1@user/testing:18d072f161b7c8d77083ca6dec0c5222f4bacf22", client.out)
        self.assertIn("PkgB/0.1@user/testing:fba7313915d1eaaa52c0a64d2f576c62e2cabd5d", client.out)
        self.assertIn("PkgC/0.1@user/testing:95cf05dd9309c4c4f3c5d8a881ff13d93481974e", client.out)
