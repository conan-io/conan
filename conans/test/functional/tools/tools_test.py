import textwrap
import unittest

from conans.test.utils.tools import TestClient


class ToolsTest(unittest.TestCase):

    def test(self):
        conanfile = textwrap.dedent("""
            from conans import ConanFile, mytools
            from conans.mytools import files
            from conans.mytools import net
            from conans.mytools.build import MyCMake

            class HelloConan(ConanFile):
                name = "hello"
                version = "0.1"

                def configure(self):
                    mytools.files.save("myfile.txt", "HELLOWORLD!")
                    content = files.load("myfile.txt")
                    self.output.info("MSG: %s" % content)
                    mytools.net.download("myurl", "myfile")
                    net.download("otherurl", "otherfile")

                def build(self):
                    cmake = mytools.build.MyCMake(self)
                    cmake.build()
                    cmake = MyCMake(self)
                    cmake.build()
            """)
        client = TestClient()
        client.save({"conanfile.py": conanfile})
        client.run("create .")
        output = str(client.out)
        self.assertIn("URL: myurl, FILE: myfile", output)
        self.assertIn("URL: otherurl, FILE: otherfile", output)
        self.assertIn("hello/0.1: MSG: HELLOWORLD!", output)
        self.assertEqual(2, output.count("hello/0.1: SUCCESS MYCMAKE"))
        self.assertEqual(2, output.count("OTHER_SUCCESS MYCMAKE"))
