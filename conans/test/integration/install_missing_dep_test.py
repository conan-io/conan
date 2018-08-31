import unittest
from conans.test.utils.tools import TestClient


class InstallMissingDependency(unittest.TestCase):

    def missing_dep_test(self):
        client = TestClient(users={"myremote": [("lasote", "mypass")]})

        # Create deps packages
        dep1_conanfile = """from conans import ConanFile
class Dep1Pkg(ConanFile):
    name = "dep1"
        """

        dep2_conanfile = """from conans import ConanFile
class Dep2Pkg(ConanFile):
    name = "dep2"
    version = "1.0"
    requires = "dep1/1.0@lasote/testing"
        """

        client.save({"conanfile.py": dep1_conanfile}, clean_first=True)
        client.run("create . dep1/1.0@lasote/testing")
        client.run("create . dep1/2.0@lasote/testing")

        client.save({"conanfile.py": dep2_conanfile}, clean_first=True)
        client.run("create . lasote/testing")

        # Create final package
        foo_conanfile = """from conans import ConanFile
class FooPkg(ConanFile):
    name = "foo"
    version = "1.0"
    requires = "dep1/{dep1_version}@lasote/testing", "dep2/1.0@lasote/testing"
        """
        client.save({"conanfile.py": foo_conanfile.format(dep1_version="1.0")}, clean_first=True)
        client.run("create . lasote/testing")

        # Bump version of one dependency
        client.save({"conanfile.py": foo_conanfile.format(dep1_version="2.0")}, clean_first=True)
        error = client.run("create . lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Can't find a 'dep2/1.0@lasote/testing' package", client.user_io.out)
        self.assertIn("- Dependencies: dep1/2.0@lasote/testing", client.user_io.out)

