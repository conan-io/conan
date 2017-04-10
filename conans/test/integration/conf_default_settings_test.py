import unittest
from conans.test.utils.tools import TestClient
from conans.util.files import save
import os
from conans import tools


class ConfDefaultSettingsTest(unittest.TestCase):

    def test_update_settings(self):
        default_conf = """[storage]
path: ~/.conan/data
[settings_defaults]
compiler=Visual Studio
compiler.version=42
"""
        client = TestClient()
        save(client.client_cache.conan_conf_path, default_conf)
        error = client.run("install Any/0.2@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'42' is not a valid 'settings.compiler.version' value", client.user_io.out)
        error = client.run('install -s compiler="Visual Studio" -s compiler.version=14',
                           ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'42' is not a valid 'settings.compiler.version' value", client.user_io.out)

        with tools.environment_append({"CONAN_ENV_COMPILER_VERSION": "14"}):
            self.assertEqual(os.environ.get("CONAN_ENV_COMPILER_VERSION"), "14")
            error = client.run('install', ignore_error=True)
            self.assertTrue(error)
            self.assertIn("'42' is not a valid 'settings.compiler.version' value",
                          client.user_io.out)
        self.assertIsNone(os.environ.get("CONAN_ENV_COMPILER_VERSION"))
