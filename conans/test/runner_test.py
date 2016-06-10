import unittest
from conans.test.tools import TestClient
import os


class RunnerTest(unittest.TestCase):

    def basic_test(self):
        conanfile = '''
from conans import ConanFile
from conans.client.runner import ConanRunner
import platform

class ConanFileToolsTest(ConanFile):

    def build(self):
        self._runner = ConanRunner()
        self.run("mkdir test_folder")
    '''
        files = {"conanfile.py": conanfile}

        client = TestClient()
        test_folder = os.path.join(client.current_folder, "test_folder")
        self.assertFalse(os.path.exists(test_folder))
        client.save(files)
        client.run("install")
        client.run("build")
        self.assertTrue(os.path.exists(test_folder))

    def cwd_test(self):
        conanfile = '''
from conans import ConanFile
from conans.client.runner import ConanRunner
import platform

class ConanFileToolsTest(ConanFile):

    def build(self):
        self._runner = ConanRunner()
        self.run("mkdir test_folder", cwd="child_folder")
    '''
        files = {"conanfile.py": conanfile}

        client = TestClient()
        os.makedirs(os.path.join(client.current_folder, "child_folder"))
        test_folder = os.path.join(client.current_folder, "child_folder", "test_folder")
        self.assertFalse(os.path.exists(test_folder))
        client.save(files)
        client.run("install")
        client.run("build")
        self.assertTrue(os.path.exists(test_folder))

    def cwd_error_test(self):
        conanfile = '''
from conans import ConanFile
from conans.client.runner import ConanRunner
import platform

class ConanFileToolsTest(ConanFile):

    def build(self):
        self._runner = ConanRunner()
        self.run("mkdir test_folder", cwd="non_existing_folder")
    '''
        files = {"conanfile.py": conanfile}

        client = TestClient()
        test_folder = os.path.join(client.current_folder, "child_folder", "test_folder")
        self.assertFalse(os.path.exists(test_folder))
        client.save(files)
        client.run("install")
        error = client.run("build", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Error while executing 'mkdir test_folder'", client.user_io.out)
        self.assertFalse(os.path.exists(test_folder))
