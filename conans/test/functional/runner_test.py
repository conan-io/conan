import unittest
from conans.test.utils.tools import TestClient
import os
from conans.client.runner import ConanRunner


class RunnerTest(unittest.TestCase):

    def _install_and_build(self, conanfile_text, runner=None):
        client = TestClient(runner=runner)
        files = {"conanfile.py": conanfile_text}
        test_folder = os.path.join(client.current_folder, "test_folder")
        self.assertFalse(os.path.exists(test_folder))
        client.save(files)
        client.run("install .")
        client.run("build .")
        return client

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
        client = self._install_and_build(conanfile)
        test_folder = os.path.join(client.current_folder, "test_folder")
        self.assertTrue(os.path.exists(test_folder))

    def log_test(self):
        conanfile = '''
from conans import ConanFile
from conans.client.runner import ConanRunner
import platform

class ConanFileToolsTest(ConanFile):

    def build(self):
        self.run("cmake --version")
    '''
        # A runner logging everything
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=True,
                             log_run_to_output=True)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertIn("--Running---", client.user_io.out)
        self.assertIn("> cmake --version", client.user_io.out)
        self.assertIn("cmake version", client.user_io.out)
        self.assertIn("Logging command output to file ", client.user_io.out)

        # A runner logging everything
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=False,
                             log_run_to_output=True)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertIn("--Running---", client.user_io.out)
        self.assertIn("> cmake --version", client.user_io.out)
        self.assertIn("cmake version", client.user_io.out)
        self.assertNotIn("Logging command output to file ", client.user_io.out)

        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=True,
                             log_run_to_output=True)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", client.user_io.out)
        self.assertNotIn("> cmake --version", client.user_io.out)
        self.assertIn("cmake version", client.user_io.out)
        self.assertIn("Logging command output to file ", client.user_io.out)

        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=False,
                             log_run_to_output=True)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", client.user_io.out)
        self.assertNotIn("> cmake --version", client.user_io.out)
        self.assertIn("cmake version", client.user_io.out)
        self.assertNotIn("Logging command output to file ", client.user_io.out)

        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=False,
                             log_run_to_output=False)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", client.user_io.out)
        self.assertNotIn("> cmake --version", client.user_io.out)
        self.assertNotIn("cmake version", client.user_io.out)
        self.assertNotIn("Logging command output to file ", client.user_io.out)

        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=True,
                             log_run_to_output=False)
        client = self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", client.user_io.out)
        self.assertNotIn("> cmake --version", client.user_io.out)
        self.assertNotIn("cmake version", client.user_io.out)
        self.assertIn("Logging command output to file ", client.user_io.out)

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
        client.run("install .")
        client.run("build .")
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
        client.run("install .")
        error = client.run("build .", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("Error while executing 'mkdir test_folder'", client.user_io.out)
        self.assertFalse(os.path.exists(test_folder))
