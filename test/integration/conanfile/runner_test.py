import textwrap

from conan.test.utils.tools import TestClient


class TestRunner:

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
        assert "RETCODE True" in client.out

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
        assert "hello Conan!" in client.out

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
        assert 'conanfile.py: Buffer got msgs Hello' in client.out

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
        assert 'conanfile.py: Buffer got stderr msgs Hello' in client.out
