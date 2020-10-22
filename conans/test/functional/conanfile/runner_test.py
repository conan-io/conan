import os
import textwrap
import unittest

import six

from conans.client.runner import ConanRunner
from conans.test.utils.tools import TestClient
from conans.test.utils.mocks import TestBufferConanOutput


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

    def test_ignore_error(self):
        conanfile = """from conans import ConanFile
class Pkg(ConanFile):
    def source(self):
        ret = self.run("not_a_command", ignore_errors=True)
        self.output.info("RETCODE %s" % (ret!=0))
"""
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("RETCODE True", client.out)

    def test_basic(self):
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

    def test_write_to_stringio(self):
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=True,
                             log_run_to_output=True)

        out = six.StringIO()
        runner("python --version", output=out)
        self.assertIn("""---Running------
> python --version
-----------------""", out.getvalue())

    def test_log(self):
        conanfile = '''
from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    def build(self):
        self.run("cmake --version")
'''
        # A runner logging everything
        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=True,
                             log_run_to_output=True,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertIn("--Running---", output)
        self.assertIn("> cmake --version", output)
        self.assertIn("cmake version", output)
        self.assertIn("Logging command output to file ", output)

        # A runner logging everything
        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=False,
                             log_run_to_output=True,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertIn("--Running---", output)
        self.assertIn("> cmake --version", output)
        self.assertIn("cmake version", output)
        self.assertNotIn("Logging command output to file ", output)

        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=True,
                             log_run_to_output=True,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", output)
        self.assertNotIn("> cmake --version", output)
        self.assertIn("cmake version", output)
        self.assertIn("Logging command output to file ", output)

        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=False,
                             log_run_to_output=True,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", output)
        self.assertNotIn("> cmake --version", output)
        self.assertIn("cmake version", output)
        self.assertNotIn("Logging command output to file ", output)

        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=False,
                             log_run_to_output=False,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", output)
        self.assertNotIn("> cmake --version", output)
        self.assertNotIn("cmake version", output)
        self.assertNotIn("Logging command output to file ", output)

        output = TestBufferConanOutput()
        runner = ConanRunner(print_commands_to_output=False,
                             generate_run_log_file=True,
                             log_run_to_output=False,
                             output=output)
        self._install_and_build(conanfile, runner=runner)
        self.assertNotIn("--Running---", output)
        self.assertNotIn("> cmake --version", output)
        self.assertNotIn("cmake version", output)
        self.assertIn("Logging command output to file ", output)

    def test_cwd(self):
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

    def test_cwd_error(self):
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
        client.run("build .", assert_error=True)
        self.assertIn("Error while executing 'mkdir test_folder'", client.out)
        self.assertFalse(os.path.exists(test_folder))

    def test_runner_capture_output(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def source(self):
                    self.run("echo 'hello Conan!'")
        """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("hello Conan!", client.out)

    def test_custom_stream_error(self):
        # https://github.com/conan-io/conan/issues/7888
        conanfile = textwrap.dedent("""
            from conans import ConanFile
            class Pkg(ConanFile):
                def source(self):
                    class Buf:
                        def __init__(self):
                            self.buf = []

                        def write(self, data):
                            self.buf.append(data)

                    my_buf = Buf()
                    self.run('echo "Hello"', output=my_buf)
                    self.output.info("Buffer got msgs {}".format(len(my_buf.buf)))
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn("Buffer got msgs 1", client.out)
