import os
import platform
import re
import subprocess
import textwrap
import unittest

import pytest

from conans.client import tools
from conans.model.ref import ConanFileReference, PackageReference
from conans.paths import CONANFILE
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer
from conans.util.runners import check_output_runner

conanfile_py = """
from conans import ConanFile

class AConan(ConanFile):
    name = "MyPackage"
    version = "0.1.0"
    short_paths=False
"""

with_deps_path_file = """
from conans import ConanFile

class BConan(ConanFile):
    name = "MyPackage2"
    version = "0.2.0"
    requires = "MyPackage/0.1.0@myUser/testing"
"""

deps_txt_file = """
[requires]
MyPackage2/0.2.0@myUser/testing
"""


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
            from conans import ConanFile

            class Pkg(ConanFile):
                options = {"myOption": [True, False]}
                def build_id(self):
                    self.info_build.options.myOption = "Any"
            """)
        client.save({CONANFILE: conanfile})
        client.run("export . pkg/0.1@user/testing")
        client.run("info pkg/0.1@user/testing --paths -o pkg:myOption=True")
        out = str(client.out).replace("\\", "/")
        self.assertIn("ID: e8618d1abf841d16789cf55a0978a47d83fb859f", out)
        self.assertIn("BuildID: 5c5eb4795e3cae1cbe06f4592b1bbd864ac68131", out)
        self.assertIn("pkg/0.1/user/testing/build/5c5eb4795e3cae1cbe06f4592b1bbd864ac68131", out)
        self.assertIn("pkg/0.1/user/testing/package/e8618d1abf841d16789cf55a0978a47d83fb859f", out)

        client.run("info pkg/0.1@user/testing --paths -o pkg:myOption=False")
        out = str(client.out).replace("\\", "/")
        self.assertIn("ID: 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", out)
        self.assertIn("BuildID: 5c5eb4795e3cae1cbe06f4592b1bbd864ac68131", out)
        self.assertIn("pkg/0.1/user/testing/build/5c5eb4795e3cae1cbe06f4592b1bbd864ac68131", out)
        self.assertIn("pkg/0.1/user/testing/package/5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9", out)

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

    @pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for short_paths")
    def test_short_paths(self):
        cache_folder = temp_folder(False)
        short_folder = os.path.join(temp_folder(False), ".cn")

        with tools.environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
            client = TestClient(cache_folder=cache_folder)
            client.save({CONANFILE: conanfile_py.replace("False", "True")})
            client.run("export . %s" % self.user_channel)
            client.run("info %s --paths" % self.reference1)
            base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
            output = client.out
            self.assertIn(os.path.join(base_path, "export"), output)
            self.assertNotIn(os.path.join(base_path, "source"), output)
            self.assertNotIn(os.path.join(base_path, "build"), output)
            self.assertNotIn(os.path.join(base_path, "package"), output)

            self.assertIn("source_folder: %s" % short_folder, output)
            self.assertIn("build_folder: %s" % short_folder, output)
            self.assertIn("package_folder: %s" % short_folder, output)

            # Ensure that the inner folders are not created (that could affect
            # pkg creation flow
            ref = ConanFileReference.loads(self.reference1)
            id_ = re.search(r'ID:\s*([a-z0-9]*)', str(client.out)).group(1)
            pref = PackageReference(ref, id_)
            for path in (client.cache.package_layout(ref, True).source(),
                         client.cache.package_layout(ref, True).build(pref),
                         client.cache.package_layout(ref, True).package(pref)):
                self.assertFalse(os.path.exists(path))
                self.assertTrue(os.path.exists(os.path.dirname(path)))

    @pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for short_paths")
    def test_short_paths_home_set_acl(self):
        """
        When CONAN_USER_HOME_SHORT is living in NTFS file systems, current user needs to be
        granted with full control permission to avoid access problems when cygwin/msys2
        windows subsystems are mounting/using that folder.
        """
        cache_folder = temp_folder(False)  # Creates a temporary folder in %HOME%\appdata\local\temp

        out = subprocess.check_output("wmic logicaldisk %s get FileSystem"
                                      % os.path.splitdrive(cache_folder)[0])
        if "NTFS" not in str(out):
            return
        short_folder = os.path.join(temp_folder(False), ".cnacls")

        self.assertFalse(os.path.exists(short_folder), "short_folder: %s shouldn't exists"
                         % short_folder)
        os.makedirs(short_folder)

        current_domain = os.environ['USERDOMAIN']
        current_user = os.environ['USERNAME']

        # Explicitly revoke full control permission to current user
        cmd = r'cacls %s /E /R "%s\%s"' % (short_folder, current_domain, current_user)
        try:
            subprocess.check_output(cmd, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception("Error %s setting ACL to short_folder: '%s'."
                            "Please check that cacls.exe exists" % (e, short_folder))

        # Run conan export in using short_folder
        with tools.environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
            client = TestClient(cache_folder=cache_folder)
            client.save({CONANFILE: conanfile_py.replace("False", "True")})
            client.run("export . %s" % self.user_channel)

        # Retrieve ACLs from short_folder
        try:
            short_folder_acls = check_output_runner("cacls %s" % short_folder,
                                                    stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception("Error %s getting ACL from short_folder: '%s'." % (e, short_folder))

        # Check user has full control
        user_acl = "%s\\%s:(OI)(CI)F" % (current_domain, current_user)
        self.assertIn(user_acl, short_folder_acls)

    def test_direct_conanfile(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("info .")
        output = client.out
        self.assertNotIn("export_folder", output)
        self.assertNotIn("source_folder", output)
        self.assertNotIn("build_folder", output)
        self.assertNotIn("package_folder", output)

    @pytest.mark.skipif(platform.system() != "Windows", reason="Needs windows for short_paths")
    def test_short_paths_folders(self):
        # https://github.com/conan-io/conan/issues/4612
        cache_folder = temp_folder(False)
        short_folder = os.path.join(temp_folder(False), ".cn")

        conanfile = textwrap.dedent("""
            from conans import ConanFile

            class Conan(ConanFile):
                short_paths=True
            """)
        with tools.environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
            client = TestClient(cache_folder=cache_folder, servers={"default": TestServer()},
                                users={"default": [("lasote", "mypass")]})
            client.save({CONANFILE: conanfile})
            client.run("export . pkga/0.1@lasote/testing")
            client.run("info pkga/0.1@lasote/testing --paths")
            self.assertIn("source_folder: %s" % short_folder, client.out)
            self.assertIn("build_folder: %s" % short_folder, client.out)
            self.assertIn("package_folder: %s" % short_folder, client.out)

            client.run("upload pkga/0.1@lasote/testing --all")
            self.assertIn("Uploading pkga/0.1@lasote/testing to remote", client.out)
            self.assertNotIn("Uploading package 1/1", client.out)
