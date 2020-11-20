import os
import unittest
import logging

from conans.client.cache.cache import CONAN_CONF
from conans.client.conf import ConanClientConfigParser
from conans.paths import DEFAULT_PROFILE_NAME
from conans.test.utils.test_files import temp_folder
from conans.util.files import save
from conans.client.tools.oss import environment_append

default_client_conf = '''[storage]
path: ~/.conan/data

[log]
trace_file = "Path/with/quotes"

[general]

'''

default_profile = '''
[settings]
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
        save(os.path.join(tmp_dir, DEFAULT_PROFILE_NAME), default_profile)
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))
        self.assertEqual(config.env_vars["CONAN_TRACE_FILE"], "Path/with/quotes")

    def test_proxies(self):
        tmp_dir = temp_folder()
        save(os.path.join(tmp_dir, CONAN_CONF), "")
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))
        self.assertEqual(None, config.proxies)
        save(os.path.join(tmp_dir, CONAN_CONF), "[proxies]")
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))
        self.assertNotIn("no_proxy", config.proxies)
        save(os.path.join(tmp_dir, CONAN_CONF), "[proxies]\nno_proxy=localhost")
        config = ConanClientConfigParser(os.path.join(tmp_dir, CONAN_CONF))
        self.assertEqual(config.proxies["no_proxy"], "localhost")


default_client_conf_log = '''[storage]
path: ~/.conan/data

[log]
trace_file = "foo/bar/quotes"
{}

[general]

'''


class ClientConfLogTest(unittest.TestCase):

    def run(self, *args, **kwargs):
        with environment_append({"CONAN_LOGGING_LEVEL": None}):
            super(ClientConfLogTest, self).run(*args, **kwargs)

    def setUp(self):
        self.tmp_dir = temp_folder()
        save(os.path.join(self.tmp_dir, DEFAULT_PROFILE_NAME), default_profile)

    def test_log_level_numbers_critical(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = 50"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.CRITICAL, config.logging_level)

    def test_log_level_numbers_debug(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = 10"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.DEBUG, config.logging_level)

    def test_log_level_numbers_invalid(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = wakawaka"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.CRITICAL, config.logging_level)

    def test_log_level_numbers_env_var_debug(self):
        with environment_append({"CONAN_LOGGING_LEVEL": "10"}):
            save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf)
            config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
            self.assertEqual(logging.DEBUG, config.logging_level)

    def test_log_level_numbers_env_var_debug_text(self):
        with environment_append({"CONAN_LOGGING_LEVEL": "WakaWaka"}):
            save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf)
            config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
            self.assertEqual(logging.CRITICAL, config.logging_level)

    def test_log_level_names_debug(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = debug"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.DEBUG, config.logging_level)

    def test_log_level_names_critical(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = Critical"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.CRITICAL, config.logging_level)

    def test_log_level_names_invalid(self):
        save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf_log.format("level = wakawaka"))
        config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
        self.assertEqual(logging.CRITICAL, config.logging_level)

    def test_log_level_names_env_var_debug(self):
        with environment_append({"CONAN_LOGGING_LEVEL": "Debug"}):
            save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf)
            config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
            self.assertEqual(logging.DEBUG, config.logging_level)

    def test_log_level_names_env_var_warning(self):
        with environment_append({"CONAN_LOGGING_LEVEL": "WARNING"}):
            save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf)
            config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
            self.assertEqual(logging.WARNING, config.logging_level)

    def test_log_level_names_env_var_invalid(self):
        with environment_append({"CONAN_LOGGING_LEVEL": "WakaWaka"}):
            save(os.path.join(self.tmp_dir, CONAN_CONF), default_client_conf)
            config = ConanClientConfigParser(os.path.join(self.tmp_dir, CONAN_CONF))
            self.assertEqual(logging.CRITICAL, config.logging_level)
