import os
import textwrap
import unittest

import pytest

from conans.paths import CONANFILE
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient

conanfile_py = """
from conan import ConanFile

class AConan(ConanFile):
    name = "MyPackage"
    version = "0.1.0"
    short_paths=False
"""

with_deps_path_file = """
from conan import ConanFile

class BConan(ConanFile):
    name = "MyPackage2"
    version = "0.2.0"
    requires = "MyPackage/0.1.0@myUser/testing"
"""

deps_txt_file = """
[requires]
MyPackage2/0.2.0@myUser/testing
"""


@pytest.mark.xfail(reason="cache2.0 revisit tests")
class InfoFoldersTest(unittest.TestCase):
    def setUp(self):
        self.user_channel = "myUser/testing"
        self.reference1 = "MyPackage/0.1.0@%s" % self.user_channel
        self.reference2 = "MyPackage2/0.2.0@%s" % self.user_channel

    def _prepare_deps(self, client):
        client.save({CONANFILE: conanfile_py})
        client.run("export . %s" % self.user_channel)
        client.save({CONANFILE: with_deps_path_file}, clean_first=True)
        client.run("export . %s" % self.user_channel)
        client.save({'conanfile.txt': deps_txt_file}, clean_first=True)

    def test_basic(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("export . %s" % self.user_channel)
        client.run("info %s --paths" % self.reference1)
        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        output = client.out
        self.assertIn(os.path.join(base_path, "export"), output)
        self.assertIn(os.path.join(base_path, "source"), output)
        self.assertIn(os.path.join(base_path, "build", NO_SETTINGS_PACKAGE_ID), output)
        self.assertIn(os.path.join(base_path, "package", NO_SETTINGS_PACKAGE_ID), output)

    def test_build_id(self):
        # https://github.com/conan-io/conan/issues/6915
        client = TestClient()
        conanfile = textwrap.dedent("""
            from conan import ConanFile

            class Pkg(ConanFile):
                options = {"myOption": [True, False]}
                def build_id(self):
                    self.info_build.options.myOption = "Any"
            """)
        client.save({CONANFILE: conanfile})
        client.run("export . --name=pkg --version=0.1 --user=user --channel=testing")
        client.run("info pkg/0.1@user/testing --paths -o pkg:myOption=True")
        out = str(client.out).replace("\\", "/")
        self.assertIn("ID: 75f77640a42abb05cd36235484f164c96ace0952", out)
        self.assertIn("BuildID: c74f42995b9d1452f1534f88b6c56ed7102212d0", out)
        self.assertIn("pkg/0.1/user/testing/build/c74f42995b9d1452f1534f88b6c56ed7102212d0", out)
        self.assertIn("pkg/0.1/user/testing/package/75f77640a42abb05cd36235484f164c96ace0952", out)

        client.run("info pkg/0.1@user/testing --paths -o pkg:myOption=False")
        out = str(client.out).replace("\\", "/")
        self.assertIn("ID: 357add7d387f11a959f3ee7d4fc9c2487dbaa604", out)
        self.assertIn("BuildID: c74f42995b9d1452f1534f88b6c56ed7102212d0", out)
        self.assertIn("pkg/0.1/user/testing/build/c74f42995b9d1452f1534f88b6c56ed7102212d0", out)
        self.assertIn("pkg/0.1/user/testing/package/357add7d387f11a959f3ee7d4fc9c2487dbaa604", out)

    def test_deps_basic(self):
        client = TestClient()
        self._prepare_deps(client)

        for ref in [self.reference2, "."]:
            client.run("info %s --paths" % ref)
            output = client.out

            base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
            self.assertIn(os.path.join(base_path, "export"), output)
            self.assertIn(os.path.join(base_path, "source"), output)

            base_path = os.path.join("MyPackage2", "0.2.0", "myUser", "testing")
            self.assertIn(os.path.join(base_path, "export"), output)
            self.assertIn(os.path.join(base_path, "source"), output)

    @pytest.mark.xfail(reason="Info command output changed")
    def test_deps_specific_information(self):
        client = TestClient()
        self._prepare_deps(client)
        client.run("info . --paths --only package_folder --package-filter MyPackage/*")
        output = client.out

        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)
        self.assertNotIn("build_folder", output)
        self.assertNotIn("MyPackage2", output)

        client.run("info . --paths --only package_folder --package-filter MyPackage*")
        output = client.out

        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)
        self.assertNotIn("build_folder", output)

        base_path = os.path.join("MyPackage2", "0.2.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)

    @pytest.mark.xfail(reason="Info command output changed")
    def test_single_field(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("export . %s" % self.user_channel)
        client.run("info %s --paths --only=build_folder" % self.reference1)
        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        output = client.out
        self.assertNotIn("export", output)
        self.assertNotIn("source", output)
        self.assertIn(os.path.join(base_path, "build"), output)
        self.assertNotIn("package", output)

    def test_direct_conanfile(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("info .")
        output = client.out
        self.assertNotIn("export_folder", output)
        self.assertNotIn("source_folder", output)
        self.assertNotIn("build_folder", output)
        self.assertNotIn("package_folder", output)
