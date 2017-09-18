import unittest

from conans.util.files import load
from conans.test.utils.tools import TestClient


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
        error = self.client.run("config get whatever", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'whatever' is not a section of conan.conf", self.client.user_io.out)
        error = self.client.run("config get whatever.what", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'whatever' is not a section of conan.conf", self.client.user_io.out)

        error = self.client.run("config get storage.what", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("'what' doesn't exist in [storage]", self.client.user_io.out)

        error = self.client.run('config set proxies=https:', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("You can't set a full section, please specify a key=value",
                      self.client.user_io.out)

        error = self.client.run('config set proxies.http:Value', ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Please specify key=value",
                      self.client.user_io.out)

    def define_test(self):
        self.client.run("config set general.fakeos=Linux")
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn("fakeos = Linux", conf_file)

        self.client.run('config set general.compiler="Other compiler"')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn('compiler = Other compiler', conf_file)

        self.client.run('config set general.compiler.version=123.4.5')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn('compiler.version = 123.4.5', conf_file)
        self.assertNotIn("14", conf_file)

        self.client.run('config set general.new_setting=mysetting ')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn('new_setting = mysetting', conf_file)

        self.client.run('config set proxies.https=myurl')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn("https = myurl", conf_file.splitlines())

    def remove_test(self):
        self.client.run('config set proxies.https=myurl')
        self.client.run('config rm proxies.https')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertNotIn('myurl', conf_file)

    def remove_section_test(self):
        self.client.run('config rm proxies')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertNotIn('[proxies]', conf_file)

    def remove_envvar_test(self):
        self.client.run('config set env.MY_VAR=MY_VALUE')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertIn('MY_VAR = MY_VALUE', conf_file)
        self.client.run('config rm env.MY_VAR')
        conf_file = load(self.client.paths.conan_conf_path)
        self.assertNotIn('MY_VAR', conf_file)
