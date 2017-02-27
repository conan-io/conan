import unittest
import os, re
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


class PackageIdTest(unittest.TestCase):
    def setUp(self):
        self.settingsA = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=12 "
                         "-s arch=x86 -s compiler.runtime=MD")

        self.settingsB = ("-s os=Windows -s compiler='Visual Studio' -s compiler.version=14 "
                          "-s arch=x86 -s compiler.runtime=MDd")
        self.userChannel = "myUser/testing"
        self.conan_ref = "MyPackage/0.1.0@%s" % self.userChannel
    def test_basic(self):
        client = TestClient()
        client.run("new %s" % self.conan_ref)
        client.run("export %s" % self.userChannel)
        for settings in [self.settingsA, self.settingsB]:
            client.run("info %s %s" % (self.conan_ref, settings))
            basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
            output = client.user_io.out;
            self.assertIn(os.path.join(basePath, "export"), output)
            self.assertIn(os.path.join(basePath, "source"), output)

            id = re.search('ID:\s*([a-z0-9]*)', str(client.user_io.out)).group(1);

            self.assertIn(os.path.join(basePath, "build", id), output)
            self.assertIn(os.path.join(basePath, "package", id), output)

    def test_short_pathes(self):
        if platform.system() == "Windows":
            currentEnv = os.environ.get("CONAN_USER_HOME_SHORT", None)
            try:
                folder = temp_folder(False);
                client = TestClient(base_folder=folder)
                client.save({CONANFILE: short_path_file})
                short_folder = os.path.join(folder, ".cn");
                os.environ["CONAN_USER_HOME_SHORT"] = short_folder
                client.run("export %s" % self.userChannel)
                for settings in [self.settingsA, self.settingsB]:
                    client.run("info %s %s" % (self.conan_ref, settings))
                    basePath = os.path.join("MyPackage", "0.1.0", "myUser", "testing");
                    output = client.user_io.out;
                    self.assertIn(os.path.join(basePath, "export"), output)
                    self.assertNotIn(os.path.join(basePath, "source"), output)
                    self.assertNotIn(os.path.join(basePath, "build"), output)
                    self.assertNotIn(os.path.join(basePath, "package"), output)

                    self.assertIn("sourceFolder: %s" % short_folder, output)
                    self.assertIn("buildFolder: %s" % short_folder, output)
                    self.assertIn("packageFolder: %s" % short_folder, output)
            finally:
                if currentEnv is None:
                    del os.environ["CONAN_USER_HOME_SHORT"]
                else:
                    os.environ["CONAN_USER_HOME_SHORT"] = currentEnv





