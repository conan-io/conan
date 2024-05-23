import os
import textwrap
import unittest

from conan.test.utils.tools import TestClient


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
        conanfile = """from conan import ConanFile
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
            from conan import ConanFile
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
            from conan import ConanFile
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

    def test_custom_stream_stderr(self):
        conanfile = textwrap.dedent("""
            from io import StringIO
            from conan import ConanFile
            class Pkg(ConanFile):
                def source(self):
                    my_buf = StringIO()
                    self.run('echo Hello 1>&2', stderr=my_buf)
                    self.output.info("Buffer got stderr msgs {}".format(my_buf.getvalue()))
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("source .")
        self.assertIn('conanfile.py: Buffer got stderr msgs Hello', client.out)
