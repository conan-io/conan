import unittest
from conans.paths import CONANFILE
from conans.test.utils.tools import TestClient
import six
import os


conanfile = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    def build(self):
        print("HEllo world")
        for k, v in {}.iteritems():
            pass
"""


class ExportLinterTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export lasote/stable")
        if six.PY2:
            self.assertIn("ERROR: Py3 incompatibility. Line 7: print statement used",
                          client.user_io.out)
            self.assertIn("ERROR: Py3 incompatibility. Line 8: Calling a dict.iter*() method",
                          client.user_io.out)

        self.assertIn("WARN: Linter. Line 8: Unused variable 'k'",
                      client.user_io.out)
        self.assertIn("WARN: Linter. Line 8: Unused variable 'v'",
                      client.user_io.out)

    def test_disable_linter(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("config set general.recipe_linter=False")
        client.run("export lasote/stable")
        self.assertNotIn("ERROR: Py3 incompatibility", client.user_io.out)
        self.assertNotIn("WARN: Linter", client.user_io.out)

    def test_custom_rc_linter(self):
        client = TestClient()
        pylintrc = """[FORMAT]
indent-string='  '
        """
        client.save({CONANFILE: conanfile,
                     "pylintrc": pylintrc})
        client.run('config set general.pylintrc="%s"'
                   % os.path.join(client.current_folder, "pylintrc"))
        client.run("export lasote/stable")
        self.assertIn("Bad indentation. Found 4 spaces, expected 2", client.user_io.out)
