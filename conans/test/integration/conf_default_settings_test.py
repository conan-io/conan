import copy
import os
import unittest
from collections import OrderedDict

from conans import tools
from conans.client.client_cache import ClientCache
from conans.client.conf.detect import detect_defaults_settings
from conans.paths import CONANFILE_TXT
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient
from conans.util.files import save


class MockOut(object):

    def writeln(self, *args, **kwargs):
        pass

    def error(self, *args, **kwargs):
        pass


class ConfDefaultSettingsTest(unittest.TestCase):

    def test_update_settings(self):
        default_profile = """[settings]
compiler=Visual Studio
compiler.version=42
arch=x86_64
compiler.runtime=MT
os=Windows

"""
        client = TestClient()
        save(client.client_cache.default_profile_path, default_profile)
        client.save({CONANFILE_TXT: ""})
        error = client.run("install Any/0.2@user/channel", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'42' is not a valid 'settings.compiler.version' value", client.user_io.out)
        client.run('install . -s compiler="Visual Studio" -s compiler.version=14')
        self.assertNotIn("'42' is not a valid 'settings.compiler.version' value", client.user_io.out)

        with tools.environment_append({"CONAN_ENV_COMPILER_VERSION": "14"}):
            client.run('install .')

        self.assertIsNone(os.environ.get("CONAN_ENV_COMPILER_VERSION"))

    def env_setting_override_test(self):
        tmp_dir = temp_folder()
        out = MockOut()
        cache = ClientCache(tmp_dir, None, out)

        base_settings = OrderedDict(detect_defaults_settings(out))

        with tools.environment_append({"CONAN_ENV_COMPILER_VERSION": "4.6"}):
            expected = copy.copy(base_settings)
            expected["compiler.version"] = "4.6"
            self.assertEquals(cache.default_profile.settings, expected)

        tmp_dir = temp_folder()
        cache = ClientCache(tmp_dir, None, out)
        with tools.environment_append({}):
            self.assertEquals(cache.default_profile.settings, base_settings)

        tmp_dir = temp_folder()
        cache = ClientCache(tmp_dir, None, out)
        # If compiler is overwritten compiler subsettings are not assigned
        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio"}):
            expected = copy.copy(base_settings)
            expected["compiler"] = "Visual Studio"
            self.assertEquals(cache.default_profile.settings, expected)

        tmp_dir = temp_folder()
        cache = ClientCache(tmp_dir, None, out)
        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio",
                                       "CONAN_ENV_COMPILER_VERSION": "14",
                                       "CONAN_ENV_COMPILER_RUNTIME": "MDd"}):
            expected = copy.copy(base_settings)
            expected["compiler"] = "Visual Studio"
            expected["compiler.runtime"] = "MDd"
            expected["compiler.version"] = "14"

            self.assertEquals(cache.default_profile.settings, expected)
