import unittest

from conan.test.assets.genconanfile import GenConanfile
from conan.test.utils.tools import TestClient


class InstallMissingDependency(unittest.TestCase):

    def test_missing_dep(self):
        client = TestClient()

        # Create deps packages
        dep1_conanfile = GenConanfile("dep1")
        client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        client.run("create . --name=dep1 --version=1.0 --user=lasote --channel=testing")
        client.run("create . --name=dep1 --version=2.0 --user=lasote --channel=testing")

        dep2_conanfile = GenConanfile("dep2", "1.0").with_require("dep1/1.0@lasote/testing")
        client.save({"conanfile.py": dep2_conanfile}, clean_first=True)
        client.run("create . --user=lasote --channel=testing")

        # Create final package
        # foo -------------> dep1/1.0
        #   \ -> dep2/1.0---->/
        conanfile = GenConanfile("foo", "1.0").with_require("dep1/1.0@lasote/testing")\
                                              .with_require("dep2/1.0@lasote/testing")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . --user=lasote --channel=testing")

        # Bump version of one dependency
        # foo -------------> dep1/2.0
        #   \ -> dep2/1.0---->/
        conanfile = GenConanfile("foo", "1.0").with_requirement("dep1/2.0@lasote/testing", force=True) \
                                              .with_require("dep2/1.0@lasote/testing")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . --user=lasote --channel=testing", assert_error=True)
        client.assert_overrides({"dep1/1.0@lasote/testing":
                                ['dep1/2.0@lasote/testing']})

        self.assertIn("Can't find a 'dep2/1.0@lasote/testing' package", client.out)
        self.assertIn("dep1/2.Y.Z", client.out)

    def test_missing_multiple_dep(self):
        client = TestClient()

        dep1_conanfile = GenConanfile()
        client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        client.run("export . --name=dep1 --version=1.0")
        client.run("export . --name=dep2 --version=1.0")

        conanfile = GenConanfile().with_require("dep1/1.0").with_require("dep2/1.0")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . --name=pkg --version=1.0", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'dep1/1.0', 'dep2/1.0'", client.out)
        self.assertIn("Try to build locally from sources using the '--build=dep1/1.0 --build=dep2/1.0'", client.out)
