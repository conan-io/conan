import os
import platform
import textwrap
import unittest


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
            from io import StringIO
            from conans import ConanFile
            class Pkg(ConanFile):
                def source(self):
                    my_buf = StringIO()
                    self.run('echo Hello', stdout=my_buf)
                    self.output.info("Buffer got msgs {}".format(my_buf.getvalue()))
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn('conanfile.py: Buffer got msgs Hello', client.out)

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
