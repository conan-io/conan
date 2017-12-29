import platform
import unittest

from conans.test.utils.tools import TestClient
from conans.util.files import load, save


class ConanSettingsPreprocessorTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()
        self.conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello0"
    version = "0.1"
    settings = "os", "compiler", "build_type"

    def configure(self):
        self.output.warn("Runtime: %s" % self.settings.get_safe("compiler.runtime"))

        '''

        files = {"conanfile.py": self.conanfile}
        self.client.save(files)
        self.client.run("export . lasote/channel")

    def test_runtime_auto(self):
        # Ensure that compiler.runtime is not declared
        self.client.run("profile new --detect default")
        default_profile = load(self.client.client_cache.default_profile_path)
        self.assertNotIn(default_profile, "compiler.runtime")
        self.client.run("install Hello0/0.1@lasote/channel --build missing")
        if platform.system() == "Windows":
            self.assertIn("Runtime: MD", self.client.user_io.out)
            self.client.run("install Hello0/0.1@lasote/channel --build missing -s build_type=Debug")
            self.assertIn("Runtime: MDd", self.client.user_io.out)

    def test_runtime_not_present_ok(self):
        # Generate the settings.yml
        self.client.run("install Hello0/0.1@lasote/channel --build missing")
        default_settings = load(self.client.client_cache.settings_path)
        default_settings = default_settings.replace("runtime:", "# runtime:")
        save(self.client.client_cache.settings_path, default_settings)
        # Ensure the runtime setting is not there anymore
        self.client.run('install Hello0/0.1@lasote/channel --build missing -s '
                        'compiler="Visual Studio" -s compiler.runtime="MDd"', ignore_error=True)
        self.assertIn("'settings.compiler.runtime' doesn't exist for 'Visual Studio'",
                      self.client.user_io.out)

        # Now install, the preprocessor shouldn't fail nor do anything
        self.client.run("install Hello0/0.1@lasote/channel --build missing")
        self.assertNotIn("Setting 'compiler.runtime' not declared, automatically",
                         self.client.user_io.out)
