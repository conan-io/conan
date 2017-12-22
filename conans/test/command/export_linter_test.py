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
        client.run("export . lasote/stable")
        self._check_linter(client.user_io.out)

    def _check_linter(self, output):
        if six.PY2:
            self.assertIn("ERROR: Py3 incompatibility. Line 7: print statement used", output)
            self.assertIn("ERROR: Py3 incompatibility. Line 8: Calling a dict.iter*() method",
                          output)
        self.assertIn("WARN: Linter. Line 8: Unused variable 'k'", output)
        self.assertIn("WARN: Linter. Line 8: Unused variable 'v'", output)

    def test_disable_linter(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("config set general.recipe_linter=False")
        client.run("export . lasote/stable")
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
        client.run("export . lasote/stable")
        self.assertIn("Bad indentation. Found 4 spaces, expected 2", client.user_io.out)

    def test_dynamic_fields(self):
        client = TestClient()
        conanfile_base = """
from conans import ConanFile
class BaseConan(ConanFile):
    name = "baselib"
    version = "1.0"
"""
        client.save({CONANFILE: conanfile_base})
        client.run("export . conan/stable")

        conanfile2 = """
from conans import ConanFile
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"

    def build(self):
        self.output.info(self.source_folder)
        self.output.info(self.package_folder)
        self.output.info(self.build_folder)

    def package(self):
        self.copy("*")

    def package_id(self):
        self.info.header_only()

    def build_id(self):
        self.output.info(str(self.info_build))

    def build_requirements(self):
        self.build_requires("baselib/1.0@conan/stable")
"""
        client.save({CONANFILE: conanfile2})
        client.run("export . lasote/stable")
        self.assertNotIn("Linter", client.user_io.out)
        # ensure nothing breaks
        client.run("install Hello/1.2@lasote/stable --build")

    def test_catch_em_all(self):
        client = TestClient()
        conanfile_base = """
from conans import ConanFile
class BaseConan(ConanFile):
    name = "baselib"
    version = "1.0"

    def source(self):
        try:
            raise Exception("Pikaaaaa!!")
        except:
            print("I got pikachu!!")

        try:
            raise Exception("Pikaaaaa!!")
        except Exception:
            print("I got pikachu!!")
"""
        client.save({CONANFILE: conanfile_base})
        client.run("export . conan/stable")
        self.assertNotIn("Linter", client.user_io.out)

    def test_warning_as_errors(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("config set general.pylint_werr=True")
        error = client.run("export . lasote/stable", ignore_error=True)
        self.assertTrue(error)
        self._check_linter(client.user_io.out)
        self.assertIn("ERROR: Package recipe has linter errors. Please fix them",
                      client.user_io.out)
