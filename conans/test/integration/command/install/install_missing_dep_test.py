import unittest

from conans.test.assets.genconanfile import GenConanfile
from conans.test.utils.tools import TestClient


class InstallMissingDependency(unittest.TestCase):

    def test_missing_dep(self):
        client = TestClient()

        # Create deps packages
        dep1_conanfile = GenConanfile("dep1")
        client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        client.run("create . dep1/1.0@lasote/testing")
        client.run("create . dep1/2.0@lasote/testing")

        dep2_conanfile = GenConanfile("dep2", "1.0").with_require("dep1/1.0@lasote/testing")
        client.save({"conanfile.py": dep2_conanfile}, clean_first=True)
        client.run("create . lasote/testing")

        # Create final package
        conanfile = GenConanfile("foo", "1.0").with_require("dep1/1.0@lasote/testing")\
                                              .with_require("dep2/1.0@lasote/testing")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . lasote/testing")

        # Bump version of one dependency
        conanfile = GenConanfile("foo", "1.0").with_require("dep1/2.0@lasote/testing") \
                                              .with_require("dep2/1.0@lasote/testing")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . lasote/testing", assert_error=True)

        self.assertIn("Can't find a 'dep2/1.0@lasote/testing' package", client.out)
        self.assertIn("- Dependencies: dep1/2.0@lasote/testing", client.out)

    def test_missing_multiple_dep(self):
        client = TestClient()

        dep1_conanfile = GenConanfile()
        client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        client.run("export . dep1/1.0@")
        client.run("export . dep2/1.0@")

        conanfile = GenConanfile().with_require("dep1/1.0").with_require("dep2/1.0")
        client.save({"conanfile.py": conanfile}, clean_first=True)
        client.run("create . pkg/1.0@", assert_error=True)
        self.assertIn("ERROR: Missing prebuilt package for 'dep1/1.0', 'dep2/1.0'", client.out)
        self.assertIn("Or try to build locally from sources with '--build=dep1 --build=dep2'", client.out)
