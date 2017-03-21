import unittest
from conans.test.utils.test_files import temp_folder
from conans.client.conf import ConanClientConfigParser, default_settings_yml
from conans.util.files import save
from conans.client.client_cache import CONAN_CONF
import os
from conans import tools
from conans.model.settings import Settings
from conans.errors import ConanException


default_client_conf = '''[storage]
path: ~/.conan/data

[log]
trace_file = "Path/with/quotes"

[proxies]
[settings_defaults]
arch=x86_64
build_type=Release
compiler=gcc
compiler.libcxx=libstdc++
compiler.version=4.9
os=Linux
'''


class ClientConfTest(unittest.TestCase):

    def test_quotes(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, CONAN_CONF), default_client_conf)
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))
        self.assertEqual(config.env_vars["CONAN_TRACE_FILE"], "Path/with/quotes")

    def env_setting_override_test(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, CONAN_CONF), default_client_conf)
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))

        # If I don't specify an ENV for compiler, the subsettings are kept,
        # except the compiler version that I'm overriding
        def get_settings():
            settings = Settings.loads(default_settings_yml)
            config.settings_defaults(settings)
            return settings.values.as_list()

        with tools.environment_append({"CONAN_ENV_COMPILER_VERSION": "4.6"}):
            self.assertEquals(get_settings(), [("arch", "x86_64"),
                                               ("build_type", "Release"),
                                               ("compiler", "gcc"),
                                               ("compiler.libcxx", "libstdc++"),
                                               ("compiler.version", "4.6"),
                                               ("os", "Linux")])
        with tools.environment_append({}):
            self.assertEquals(get_settings(), [("arch", "x86_64"),
                                               ("build_type", "Release"),
                                               ("compiler", "gcc"),
                                               ("compiler.libcxx", "libstdc++"),
                                               ("compiler.version", "4.9"),
                                               ("os", "Linux")])

        # If compiler is overwritten compiler subsettings are not assigned
        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio"}):
            self.assertEquals(get_settings(), [("arch", "x86_64"),
                                               ("build_type", "Release"),
                                               ("compiler", "Visual Studio"),
                                               ("os", "Linux")])

        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio",
                                       "CONAN_ENV_COMPILER_VERSION": "14",
                                       "CONAN_ENV_COMPILER_RUNTIME": "MDd"}):
            self.assertEquals(dict(get_settings()), dict([("arch", "x86_64"),
                                                          ("build_type", "Release"),
                                                          ("compiler", "Visual Studio"),
                                                          ("compiler.version", "14"),
                                                          ("compiler.runtime", "MDd"),
                                                          ("os", "Linux")]))

        # Specified settings are applied in order (first fake and then fake.setting)
        with tools.environment_append({"CONAN_ENV_FAKE": "Fake1"}):
            self.assertRaisesRegexp(ConanException, "'settings.fake' doesn't exist", get_settings)
