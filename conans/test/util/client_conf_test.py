import os
import unittest

from conans.client.client_cache import CONAN_CONF
from conans.client.conf import ConanClientConfigParser
from conans.paths import DEFAULT_PROFILE_NAME
from conans.test.utils.test_files import temp_folder
from conans.util.files import save


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
