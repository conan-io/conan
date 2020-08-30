import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ToolsTest(unittest.TestCase):

    def test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, mytools
            from conans.tools import load


            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"

                def configure(self):
                    mytools.files.save("myfile.txt", "HELLOWORLD!")
                    content = load("myfile.txt")
                    self.output.info("MSG: %s" % content)
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create .")
        self.assertIn("hello/0.1: MSG: HELLOWORLD!", client.out)
