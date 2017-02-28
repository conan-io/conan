import unittest
import os, re

from conans import tools
from conans.test.tools import TestClient
from conans.test.utils.test_files import temp_folder
from conans.paths import CONANFILE
import platform

short_path_file = """
from conans import ConanFile

class AConan(ConanFile):
    name = "MyPackage"
    version = "0.1.0"
    short_paths=True
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
        self.settings = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=12 "
                         "-s arch=x86 -s compiler.runtime=MD")

        self.userChannel = "myUser/testing"
        self.conan_ref = "MyPackage/0.1.0@%s" % self.userChannel
        self.conan_ref2 = "MyPackage2/0.2.0@%s" % self.userChannel

    def _prepare_deps(self, client):
        client.run("new %s" % self.conan_ref)
        client.run("export %s" % self.userChannel)
        client.save({CONANFILE: with_deps_path_file}, clean_first=True)
        client.run("export %s" % self.userChannel)
        client.save({'conanfile.txt': deps_txt_file}, clean_first=True)

    def test_basic(self):
        client = TestClient()
        client.run("new %s" % self.conan_ref)
        client.run("export %s" % self.userChannel)
        client.run("info %s %s" % (self.conan_ref, self.settings))
        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        output = client.user_io.out;
        self.assertIn(os.path.join(basePath, "export"), output)
        self.assertIn(os.path.join(basePath, "source"), output)
        id = re.search('ID:\s*([a-z0-9]*)', str(client.user_io.out)).group(1);
        self.assertIn(os.path.join(basePath, "build", id), output)
        self.assertIn(os.path.join(basePath, "package", id), output)

    def test_deps_basic(self):
        client = TestClient()
        self._prepare_deps(client)
        client.run("info %s %s" % (self.conan_ref2, self.settings))
        output = client.user_io.out;

        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "export"), output)
        self.assertIn(os.path.join(basePath, "source"), output)

        basePath = os.path.join("MyPackage2", "0.2.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "export"), output)
        self.assertIn(os.path.join(basePath, "source"), output)

    def test_deps_conanfile_txt(self):
        client = TestClient()
        self._prepare_deps(client)
        client.run("info %s" % (self.settings))
        output = client.user_io.out;

        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "export"), output)
        self.assertIn(os.path.join(basePath, "source"), output)

        basePath = os.path.join("MyPackage2", "0.2.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "export"), output)
        self.assertIn(os.path.join(basePath, "source"), output)

    def test_deps_specific_information(self):
        client = TestClient()
        self._prepare_deps(client)
        client.run("info --only package_folder --package_filter MyPackage/* %s" % (self.settings))
        output = client.user_io.out;

        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "package"), output)
        self.assertNotIn(os.path.join(basePath, "build"), output)

        basePath = os.path.join("MyPackage2", "0.2.0", "myUser", "testing");
        self.assertNotIn(os.path.join(basePath, "package"), output)

        client.run("info --only package_folder --package_filter MyPackage* %s" % (self.settings))
        output = client.user_io.out;

        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "package"), output)
        self.assertNotIn(os.path.join(basePath, "build"), output)

        basePath = os.path.join("MyPackage2", "0.2.0", "myUser", "testing");
        self.assertIn(os.path.join(basePath, "package"), output)


    def test_single_field(self):
        client = TestClient()
        client.run("new %s" % self.conan_ref)
        client.run("export %s" % self.userChannel)
        client.run("info --only=build_folder %s %s" % (self.conan_ref, self.settings))
        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        output = client.user_io.out;
        self.assertNotIn(os.path.join(basePath, "export"), output)
        self.assertNotIn(os.path.join(basePath, "source"), output)
        self.assertIn(os.path.join(basePath, "build"), output)
        self.assertNotIn(os.path.join(basePath, "package"), output)

    def test_short_paths(self):
        if platform.system() == "Windows":
            folder = temp_folder(False);
            short_folder = os.path.join(folder, ".cn");
            with tools.environment_append({"CONAN_USER_HOME_SHORT": short_folder}):
                client = TestClient(base_folder=folder)
                client.save({CONANFILE: short_path_file})
                client.run("export %s" % self.userChannel)
                client.run("info %s %s" % (self.conan_ref, self.settings))
                basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
                output = client.user_io.out;
                self.assertIn(os.path.join(basePath, "export"), output)
                self.assertNotIn(os.path.join(basePath, "source"), output)
                self.assertNotIn(os.path.join(basePath, "build"), output)
                self.assertNotIn(os.path.join(basePath, "package"), output)

                self.assertIn("sourceFolder: %s" % short_folder, output)
                self.assertIn("buildFolder: %s" % short_folder, output)
                self.assertIn("packageFolder: %s" % short_folder, output)

    def test_direct_conanfile(self):
        client = TestClient()
        client.run("new %s" % self.conan_ref)
        client.run("info %s" % (self.settings))
        basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
        output = client.user_io.out;
        self.assertNotIn("exportFolder", output)
        self.assertNotIn("sourceFolder", output)
        self.assertNotIn("buildFolder", output)
        self.assertNotIn("packageFolder", output)
