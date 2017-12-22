import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import save
import os


class SettingConstraintTest(unittest.TestCase):

    def settings_constraint_test(self):
        conanfile = """from conans import ConanFile
class Test(ConanFile):
    name = "Hello"
    version = "0.1"
    settings = {"compiler": {"gcc": {"version": ["7.1"]}}}
    def build(self):
        self.output.info("Compiler version!: %s" % self.settings.compiler.version)
    """
        test = """from conans import ConanFile
class Test(ConanFile):
    requires = "Hello/0.1@user/channel"
    def test(self):
        pass
    """
        client = TestClient()
        client.save({"conanfile.py": conanfile,
                     "test_package/conanfile.py": test})
        default_profile = os.path.join(client.base_folder, ".conan/profiles/default")
        save(default_profile, "[settings]\ncompiler=gcc\ncompiler.version=6.3")
        error = client.run("create . user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Invalid setting '6.3' is not a valid 'settings.compiler.version'",
                      client.user_io.out)
        client.run("create . user/channel -s compiler=gcc -s compiler.version=7.1")
        self.assertIn("Hello/0.1@user/channel: Compiler version!: 7.1", client.user_io.out)
        self.assertIn("Hello/0.1@user/channel: Generating the package", client.user_io.out)
