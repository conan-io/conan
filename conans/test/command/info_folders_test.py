import unittest
import os
import platform
import re
import subprocess

from conans import tools
from conans.test.utils.tools import TestClient
from conans.test.utils.test_files import temp_folder
from conans.paths import CONANFILE
from conans.model.ref import ConanFileReference, PackageReference


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
        self.conan_ref = "MyPackage/0.1.0@%s" % self.user_channel
        self.conan_ref2 = "MyPackage2/0.2.0@%s" % self.user_channel

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
        client.run("info %s --paths" % (self.conan_ref))
        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        output = client.user_io.out
        self.assertIn(os.path.join(base_path, "export"), output)
        self.assertIn(os.path.join(base_path, "source"), output)
        id_ = "5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9"
        self.assertIn(os.path.join(base_path, "build", id_), output)
        self.assertIn(os.path.join(base_path, "package", id_), output)

    def test_deps_basic(self):
        client = TestClient()
        self._prepare_deps(client)

        for ref in [self.conan_ref2, "."]:
            client.run("info %s --paths" % (ref))
            output = client.user_io.out

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
        output = client.user_io.out

        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)
        self.assertNotIn("build", output)
        self.assertNotIn("MyPackage2", output)

        client.run("info . --paths --only package_folder --package-filter MyPackage*")
        output = client.user_io.out

        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)
        self.assertNotIn("build", output)

        base_path = os.path.join("MyPackage2", "0.2.0", "myUser", "testing")
        self.assertIn(os.path.join(base_path, "package"), output)

    def test_single_field(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("export . %s" % self.user_channel)
        client.run("info %s --paths --only=build_folder" % (self.conan_ref))
        base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
        output = client.user_io.out
        self.assertNotIn("export", output)
        self.assertNotIn("source", output)
        self.assertIn(os.path.join(base_path, "build"), output)
        self.assertNotIn("package", output)

    def test_short_paths(self):
        if platform.system() != "Windows":
            return
        folder = temp_folder(False)
        short_folder = os.path.join(folder, ".cn")

        with tools.environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
            client = TestClient(base_folder=folder)
            client.save({CONANFILE: conanfile_py.replace("False", "True")})
            client.run("export . %s" % self.user_channel)
            client.run("info %s --paths" % (self.conan_ref))
            base_path = os.path.join("MyPackage", "0.1.0", "myUser", "testing")
            output = client.user_io.out
            self.assertIn(os.path.join(base_path, "export"), output)
            self.assertNotIn(os.path.join(base_path, "source"), output)
            self.assertNotIn(os.path.join(base_path, "build"), output)
            self.assertNotIn(os.path.join(base_path, "package"), output)

            self.assertIn("source_folder: %s" % short_folder, output)
            self.assertIn("build_folder: %s" % short_folder, output)
            self.assertIn("package_folder: %s" % short_folder, output)

            # Ensure that the inner folders are not created (that could affect
            # pkg creation flow
            ref = ConanFileReference.loads(self.conan_ref)
            id_ = re.search('ID:\s*([a-z0-9]*)', str(client.user_io.out)).group(1)
            pkg_ref = PackageReference(ref, id_)
            for path in (client.client_cache.source(ref, True),
                         client.client_cache.build(pkg_ref, True),
                         client.client_cache.package(pkg_ref, True)):
                self.assertFalse(os.path.exists(path))
                self.assertTrue(os.path.exists(os.path.dirname(path)))

    def test_short_paths_home_set_acl(self):
        """
        When CONAN_USER_HOME_SHORT is living in NTFS file systems, current user needs to be
        granted with full control permission to avoid access problems when cygwin/msys2 windows subsystems
        are mounting/using that folder.
        """
        if platform.system() != "Windows":
            return

        folder = temp_folder(False)  # Creates a temporary folder in %HOME%\appdata\local\temp

        out = subprocess.check_output("wmic logicaldisk %s get FileSystem" % os.path.splitdrive(folder)[0])
        if "NTFS" not in str(out):
            return
        short_folder = os.path.join(folder, ".cnacls")

        self.assertFalse(os.path.exists(short_folder), "short_folder: %s shouldn't exists" % short_folder)
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
            client = TestClient(base_folder=folder)
            client.save({CONANFILE: conanfile_py.replace("False", "True")})
            client.run("export . %s" % self.user_channel)

        # Retrieve ACLs from short_folder
        try:
            short_folder_acls = subprocess.check_output("cacls %s" % short_folder, stderr=subprocess.STDOUT)
        except subprocess.CalledProcessError as e:
            raise Exception("Error %s getting ACL from short_folder: '%s'." % (e, short_folder))

        # Check user has full control
        user_acl = "%s\\%s:(OI)(CI)F" % (current_domain, current_user)
        self.assertIn(user_acl.encode(), short_folder_acls)

    def test_direct_conanfile(self):
        client = TestClient()
        client.save({CONANFILE: conanfile_py})
        client.run("info .")
        output = client.user_io.out
        self.assertNotIn("export_folder", output)
        self.assertNotIn("source_folder", output)
        self.assertNotIn("build_folder", output)
        self.assertNotIn("package_folder", output)
