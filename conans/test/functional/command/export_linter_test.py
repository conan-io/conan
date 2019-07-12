import os
import unittest

import six
from mock import patch

from conans.client import tools
from conans.paths import CONANFILE, DATA_YML
from conans.test.utils.tools import TestClient

conanfile = """
from conans import ConanFile, tools
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"
    def build(self):
        print("HEllo world")
        for k, v in {}.iteritems():
            pass
        tools.msvc_build_command(self.settings, "path")
"""


@patch.dict('os.environ', {"CONAN_RECIPE_LINTER": "True"})
class ExportLinterTest(unittest.TestCase):

    def test_basic(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . lasote/stable")
        self._check_linter(client.out)

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
        with tools.environment_append({"CONAN_RECIPE_LINTER": "False"}):
            client.run("export . lasote/stable")
            self.assertNotIn("ERROR: Py3 incompatibility", client.out)
            self.assertNotIn("WARN: Linter", client.out)

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
        self.assertIn("Bad indentation. Found 4 spaces, expected 2", client.out)

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
from conans import ConanFile, python_requires

python_requires("baselib/1.0@conan/stable")
class TestConan(ConanFile):
    name = "Hello"
    version = "1.2"

    def build(self):
        self.output.info(self.source_folder)
        self.output.info(self.package_folder)
        self.output.info(self.build_folder)
        self.output.info(self.install_folder)

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
        self.assertNotIn("Linter", client.out)
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
        self.assertNotIn("Failed pylint", client.out)
        self.assertNotIn("Linter", client.out)

    def test_warning_as_errors(self):
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("config set general.pylint_werr=True")
        client.run("export . lasote/stable", assert_error=True)
        self._check_linter(client.out)
        self.assertIn("ERROR: Package recipe has linter errors. Please fix them",
                      client.out)

    def export_deploy_test(self):
        conanfile = """
from conans import ConanFile
class BaseConan(ConanFile):
    name = "baselib"
    version = "1.0"

    def deploy(self):
        self.copy_deps("*.dll")
"""
        client = TestClient()
        client.save({CONANFILE: conanfile})
        client.run("export . conan/stable")
        self.assertNotIn("Failed pylint", client.out)
        self.assertNotIn("Linter warnings", client.out)
        self.assertNotIn("WARN: Linter. Line 8: Instance of 'BaseConan' has no 'copy_deps' member",
                         client.out)
        self.assertNotIn("WARN: Linter. Line 8: self.copy_deps is not callable",
                         client.out)

    def test_conan_data(self):
        client = TestClient()
        conanfile = """
from conans import ConanFile
class ExampleConan(ConanFile):
    name = "example"

    def build(self):
        print(self.conan_data["sources"][float(self.version)])
"""
        conandata = """sources:
  2.3:
    url: "https://github.com/google/cctz/archive/v2.3.tar.gz"
    sha256: "8615b20d4e33e02a271c3b93a3b208e3d7d5d66880f5f6208b03426e448f32db"
"""
        client.save({DATA_YML: conandata})
        client.save({CONANFILE: conanfile})
        client.run("export . 2.3@conan/stable")
        self.assertNotIn("Linter.", client.out)
        self.assertNotIn("Instance of 'ExampleConan' has no 'conan_data' member", client.out)
