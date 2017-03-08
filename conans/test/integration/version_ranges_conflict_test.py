import unittest
from conans.test.tools import TestClient, TestServer
from conans.paths import CONANFILE
from conans.util.files import load
import os


class VersionRangesConflictTest(unittest.TestCase):


    conanfileA = """
from conans import ConanFile, CMake
import os
class MyConanA(ConanFile):
    name = "MyPkg1"
    version = "%s"
    """

    conanfileB = """
from conans import ConanFile, CMake
import os
class MyConanB(ConanFile):
    name = "MyPkg2"
    version = "0.1"
    requires = "MyPkg1/[~0.1]@user/testing"
    """

    conanfileC = """
from conans import ConanFile, CMake
import os
class MyConanC(ConanFile):
    name = "MyPkg3"
    version = "0.1"
    requires = "MyPkg1/[~0.2]@user/testing", "MyPkg2/[~0.1]@user/testing"
    """

    def _prepareClient(self):
        client = TestClient()
        client.save({CONANFILE: self.conanfileA % "0.1.0"})
        client.run("export user/testing")
        client.save({CONANFILE: self.conanfileA % "0.2.0"})
        client.run("export user/testing")
        client.save({CONANFILE: self.conanfileB})
        client.run("export user/testing")
        client.save({CONANFILE: self.conanfileC})
        return client

    def werror_warn_test(self):
        client = self._prepareClient()
        client.run("info")
        self.assertIn("WARN: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'", client.user_io.out)

    def werror_fail_test(self):
        client = self._prepareClient()
        client.run("install --build --werror", ignore_error=True)

        print(client.user_io.out)

        self.assertNotIn("WARN: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                      "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'", client.user_io.out)

        self.assertIn("ERROR: Version range '~0.1' required by 'MyPkg2/0.1@user/testing' "
                         "not valid for downstream requirement 'MyPkg1/0.2.0@user/testing'", client.user_io.out)
