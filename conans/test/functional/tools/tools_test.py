import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ToolsTest(unittest.TestCase):

    def test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, mytools

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"

                def configure(self):
                    mytools.files.save("myfile.txt", "HELLOWORLD!")
                    content = mytools.files.load("myfile.txt")
                    self.output.info("MSG: %s" % content)
                    mytools.net.download("myurl", "myfile")

                def build(self):
                    cmake = mytools.build.MyCMake(self)
                    cmake.build()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create .")
        self.assertIn("URL: myurl, FILE: myfile", client.out)
        self.assertIn("hello/0.1: MSG: HELLOWORLD!", client.out)
        self.assertIn("hello/0.1: SUCCESS MYCMAKE", client.out)
        self.assertIn("hello/0.1: OTHER_SUCCESS MYCMAKE", client.out)
