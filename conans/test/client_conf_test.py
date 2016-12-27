import unittest
from conans.test.utils.test_files import temp_folder
from conans.client.conf import ConanClientConfigParser
from conans.util.files import save
from conans.client.client_cache import CONAN_CONF
import os
from conans import tools


default_client_conf = '''[storage]
path: ~/.conan/data

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

    def env_setting_override_test(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, CONAN_CONF), default_client_conf)
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))

        # If I don't specify an ENV for compiler, the subsettings are kept,
        # except the compiler version that I'm overriding
        with tools.environment_append({"CONAN_ENV_COMPILER_VERSION": "4.6"}):
            settings = config.settings_defaults
            self.assertEquals(settings.as_list(), [("arch", "x86_64"),
                                                   ("build_type", "Release"),
                                                   ("compiler", "gcc"),
                                                   ("compiler.libcxx", "libstdc++"),
                                                   ("compiler.version", "4.6"),
                                                   ("os", "Linux")])
        with tools.environment_append({}):
            settings = config.settings_defaults
            self.assertEquals(settings.as_list(), [("arch", "x86_64"),
                                                   ("build_type", "Release"),
                                                   ("compiler", "gcc"),
                                                   ("compiler.libcxx", "libstdc++"),
                                                   ("compiler.version", "4.9"),
                                                   ("os", "Linux")])

        # If compiler is overwritten compiler subsettings are not assigned
        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio"}):
            settings = config.settings_defaults
            self.assertEquals(settings.as_list(), [("arch", "x86_64"),
                                                   ("build_type", "Release"),
                                                   ("compiler", "Visual Studio"),
                                                   ("os", "Linux")])

        with tools.environment_append({"CONAN_ENV_COMPILER": "Visual Studio",
                                       "CONAN_ENV_COMPILER_VERSION": "14",
                                       "CONAN_ENV_COMPILER_RUNTIME": "MDd"}):
            settings = config.settings_defaults
            self.assertEquals(dict(settings.as_list()), dict([("arch", "x86_64"),
                                                              ("build_type", "Release"),
                                                              ("compiler", "Visual Studio"),
                                                              ("compiler.version", "14"),
                                                              ("compiler.runtime", "MDd"),
                                                              ("os", "Linux")]))

        # Specified settings are applied in order (first fake and then fake.setting)
        with tools.environment_append({"CONAN_ENV_FAKE": "Fake1",
                                       "CONAN_ENV_FAKE_SETTING": "Fake"}):
            settings = config.settings_defaults
            self.assertEquals(dict(settings.as_list()), dict([("arch", "x86_64"),
                                                              ("build_type", "Release"),
                                                              ("compiler", "gcc"),
                                                              ("compiler.libcxx", "libstdc++"),
                                                              ("compiler.version", "4.9"),
                                                              ("os", "Linux"),
                                                              ("fake", "Fake1"),
                                                              ("fake.setting", "Fake")]))
