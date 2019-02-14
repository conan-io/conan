import unittest

import mock

from conans.test.utils.tools import NO_SETTINGS_PACKAGE_ID, TestClient, TestServer


class ConanGetTest(unittest.TestCase):

    def setUp(self):
        self.conanfile = '''
from conans import ConanFile

class HelloConan(ConanFile):
    name = "Hello0"
    version = "0.1"
    exports_sources = "path*"
    exports = "other*"
        '''

        test_server = TestServer([],  # write permissions
                                 users={"lasote": "mypass"})  # exported users and passwords
        servers = {"default": test_server}
        self.client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        files = {"conanfile.py": self.conanfile, "path/to/exported_source": "1",
                 "other/path/to/exported": "2"}
        self.client.save(files)
        self.client.run("export . lasote/channel")
        self.client.run("install Hello0/0.1@lasote/channel --build missing")

    def test_get_local(self):
        # Local search, dir list
        self.client.run('get Hello0/0.1@lasote/channel .')
        self.assertEquals("""Listing directory '.':
 conanfile.py
 conanmanifest.txt
 other
""", self.client.user_io.out)

        self.client.run('get Hello0/0.1@lasote/channel other --raw')
        self.assertEquals("path\n", self.client.user_io.out)

        self.client.run('get Hello0/0.1@lasote/channel other/path --raw')
        self.assertEquals("to\n", self.client.user_io.out)

        self.client.run('get Hello0/0.1@lasote/channel other/path/to')
        self.assertEquals("Listing directory 'other/path/to':\n exported\n",
                          self.client.user_io.out)

        self.client.run('get Hello0/0.1@lasote/channel other/path/to/exported')
        self.assertEquals("2\n", self.client.user_io.out)

        # Local search, conanfile print
        self.client.run('get Hello0/0.1@lasote/channel --raw')
        self.assertIn(self.conanfile, self.client.user_io.out)

        # Get conanfile, verify the formatter applied
        def verify_python_lexer(contents, lexer, formatter):
            from pygments.lexers import PythonLexer
            self.assertIsInstance(lexer, PythonLexer)
            self.assertIn("class HelloConan", contents)
            return "Hi there! I'm a mock!"

        with mock.patch("pygments.highlight", verify_python_lexer):
            with mock.patch("conans.client.output.ConanOutput.is_terminal", True):
                self.client.run('get Hello0/0.1@lasote/channel')
        self.assertIn("Hi there! I'm a mock!", self.client.out)

        # Local search print package info
        self.client.run('get Hello0/0.1@lasote/channel -p %s --raw' % NO_SETTINGS_PACKAGE_ID)
        self.assertIn("""
[requires]


[options]


[full_settings]


[full_requires]


[full_options]


[recipe_hash]
    dcb3ad84f4e46fb3da40dbbea0017094

""", self.client.user_io.out)

        # List package dir
        self.client.run('get Hello0/0.1@lasote/channel "." -p %s --raw' % NO_SETTINGS_PACKAGE_ID)
        self.assertEquals("conaninfo.txt\nconanmanifest.txt\n", self.client.user_io.out)

    def test_get_remote(self):
        self.client.run('upload "Hello*" --all -c')

        # Remote search, dir list
        self.client.run('get Hello0/0.1@lasote/channel . -r default --raw')
        self.assertIn("conan_export.tgz\nconan_sources.tgz\nconanfile.py\nconanmanifest.txt",
                      self.client.user_io.out)

        # Remote search, conanfile print
        self.client.run('get Hello0/0.1@lasote/channel -r default --raw')
        self.assertIn(self.conanfile, self.client.user_io.out)

        # List package dir
        self.client.run('get Hello0/0.1@lasote/channel "." '
                        '  -p %s --raw -r default' % NO_SETTINGS_PACKAGE_ID)
        self.assertEquals("conan_package.tgz\nconaninfo.txt\nconanmanifest.txt\n",
                          self.client.user_io.out)

    def test_not_found(self):
        self.client.run('get Hello0/0.1@lasote/channel "." -r default', assert_error=True)
        self.assertIn("Recipe not found: 'Hello0/0.1@lasote/channel'", self.client.user_io.out)

        self.client.run('get Hello0/0.1@lasote/channel "." -r default -p 123123123123123',
                        assert_error=True)
        if self.client.cache.config.revisions_enabled:
            # It has to resolve the latest so it fails again with the recipe
            self.assertIn("Recipe not found: 'Hello0/0.1@lasote/channel'", self.client.user_io.out)
        else:
            self.assertIn("Binary package not found: 'Hello0/0.1@lasote/channel:123123123123123'",
                          self.client.user_io.out)
