import unittest

from conans.test.utils.tools import TestClient
from conans.util.files import load


class ConfigTest(unittest.TestCase):

    def setUp(self):
        self.client = TestClient()

    def basic_test(self):
        # show the full file
        self.client.run("config get")
        self.assertIn("default_profile = default", self.client.user_io.out)
        self.assertIn("path = ~/.conan/data", self.client.user_io.out)

    def storage_test(self):
        # show the full file
        self.client.run("config get storage")
        self.assertIn("path = ~/.conan/data", self.client.user_io.out)

        self.client.run("config get storage.path")
        self.assertIn("~/.conan/data", self.client.user_io.out)
        self.assertNotIn("path:", self.client.user_io.out)

    def errors_test(self):
        self.client.run("config get whatever", assert_error=True)
        self.assertIn("'whatever' is not a section of conan.conf", self.client.user_io.out)
        self.client.run("config get whatever.what", assert_error=True)
        self.assertIn("'whatever' is not a section of conan.conf", self.client.user_io.out)
        self.client.run("config get storage.what", assert_error=True)
        self.assertIn("'what' doesn't exist in [storage]", self.client.user_io.out)
        self.client.run('config set proxies=https:', assert_error=True)
        self.assertIn("You can't set a full section, please specify a key=value",
                      self.client.user_io.out)

        self.client.run('config set proxies.http:Value', assert_error=True)
        self.assertIn("Please specify 'key=value'", self.client.user_io.out)

    def define_test(self):
        self.client.run("config set general.fakeos=Linux")
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn("fakeos = Linux", conf_file)

        self.client.run('config set general.compiler="Other compiler"')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn('compiler = Other compiler', conf_file)

        self.client.run('config set general.compiler.version=123.4.5')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn('compiler.version = 123.4.5', conf_file)
        self.assertNotIn("14", conf_file)

        self.client.run('config set general.new_setting=mysetting ')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn('new_setting = mysetting', conf_file)

        self.client.run('config set proxies.https=myurl')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn("https = myurl", conf_file.splitlines())

    def set_with_weird_path_test(self):
        # https://github.com/conan-io/conan/issues/4110
        self.client.run("config set log.trace_file=/recipe-release%2F0.6.1")
        self.client.run("config get log.trace_file")
        self.assertIn("/recipe-release%2F0.6.1", self.client.out)

    def remove_test(self):
        self.client.run('config set proxies.https=myurl')
        self.client.run('config rm proxies.https')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertNotIn('myurl', conf_file)

    def remove_section_test(self):
        self.client.run('config rm proxies')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertNotIn('[proxies]', conf_file)

    def remove_envvar_test(self):
        self.client.run('config set env.MY_VAR=MY_VALUE')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertIn('MY_VAR = MY_VALUE', conf_file)
        self.client.run('config rm env.MY_VAR')
        conf_file = load(self.client.client_cache.conan_conf_path)
        self.assertNotIn('MY_VAR', conf_file)
