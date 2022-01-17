import os
import platform
import textwrap
import unittest
from io import StringIO

import pytest

from conans.client.runner import ConanRunner
from conans.util.env import environment_update
from conans.test.utils.tools import TestClient


class RunnerTest(unittest.TestCase):

    def _install_and_build(self, client, conanfile_text):
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
        client = TestClient()
        self._install_and_build(client, conanfile)
        test_folder = os.path.join(client.current_folder, "test_folder")
        self.assertTrue(os.path.exists(test_folder))

    def test_write_to_stringio(self):
        runner = ConanRunner(print_commands_to_output=True,
                             generate_run_log_file=True,
                             log_run_to_output=True)

        out = StringIO()
        runner("python --version", output=out)
        self.assertIn("""---Running------
> python --version
-----------------""", out.getvalue())

    @pytest.mark.tool_cmake
    def test_log(self):
        conanfile = '''
from conans import ConanFile

class ConanFileToolsTest(ConanFile):
    def build(self):
        self.run("cmake --version")
'''
        # A runner logging everything
        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=True
                            run_to_file=True
                            run_to_output=True
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        self._install_and_build(client, conanfile)
        self.assertIn("--Running---", client.out)
        self.assertIn("> cmake --version", client.out)
        self.assertIn("cmake version", client.out)
        self.assertIn("Logging command output to file ", client.out)

        # A runner logging everything
        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=True
                            run_to_file=False
                            run_to_output=True
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        self._install_and_build(client, conanfile)
        self.assertIn("--Running---", client.out)
        self.assertIn("> cmake --version", client.out)
        self.assertIn("cmake version", client.out)
        self.assertNotIn("Logging command output to file ", client.out)

        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=False
                            run_to_file=True
                            run_to_output=True
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        self._install_and_build(client, conanfile)
        self.assertNotIn("--Running---", client.out)
        self.assertNotIn("> cmake --version", client.out)
        self.assertIn("cmake version", client.out)
        self.assertIn("Logging command output to file ", client.out)

        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=False
                            run_to_file=False
                            run_to_output=True
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        self._install_and_build(client, conanfile)
        self.assertNotIn("--Running---", client.out)
        self.assertNotIn("> cmake --version", client.out)
        self.assertIn("cmake version", client.out)
        self.assertNotIn("Logging command output to file ", client.out)

        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=False
                            run_to_file=False
                            run_to_output=False
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)

        self._install_and_build(client, conanfile)
        self.assertNotIn("--Running---", client.out)
        self.assertNotIn("> cmake --version", client.out)
        self.assertNotIn("cmake version", client.out)
        self.assertNotIn("Logging command output to file ", client.out)

        client = TestClient()
        conan_conf = textwrap.dedent("""
                            [storage]
                            path = ./data
                            [log]
                            print_run_commands=False
                            run_to_file=True
                            run_to_output=False
                        """)
        client.save({"conan.conf": conan_conf}, path=client.cache.cache_folder)
        self._install_and_build(client, conanfile)
        self.assertNotIn("--Running---", client.out)
        self.assertNotIn("> cmake --version", client.out)
        self.assertNotIn("cmake version", client.out)
        self.assertIn("Logging command output to file ", client.out)

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

    def test_credentials_removed(self):
        conanfile = textwrap.dedent("""
            import os
            import platform
            from conans import ConanFile

            class Recipe(ConanFile):
                def export(self):
                    self.output.info(">> key: {}<<".format(os.getenv('CONAN_LOGIN_ENCRYPTION_KEY')))
                    self.output.info(">> var: {}<<".format(os.getenv('OTHER_VAR')))
                    if platform.system() == 'Windows':
                        self.run("echo key: %CONAN_LOGIN_ENCRYPTION_KEY%--")
                        self.run("echo var: %OTHER_VAR%--")
                    else:
                        self.run("echo key: $CONAN_LOGIN_ENCRYPTION_KEY--")
                        self.run("echo var: $OTHER_VAR--")
        """)
        with environment_update({'CONAN_LOGIN_ENCRYPTION_KEY': 'secret!', 'OTHER_VAR': 'other_var'}):
            client = TestClient()
            client.save({"conanfile.py": conanfile})
            client.run("export . --name=name --version=version")
            self.assertIn("name/version: >> key: secret!<<", client.out)
            self.assertIn("name/version: >> var: other_var<<", client.out)
            if platform.system() == 'Windows':
                self.assertIn("key: %CONAN_LOGIN_ENCRYPTION_KEY%--", client.out)
            else:
                self.assertIn("key: --", client.out)
            self.assertIn("var: other_var--", client.out)
