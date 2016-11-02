import unittest
from conans.test.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os


conanfile = """from conans import ConanFile

class ConanToolPackage(ConanFile):
    name = "conantool"
    version = "1.0"
    exports = "*"
    build_policy = "missing"

    def package(self):
        self.copy("*")

    def package_info(self):
        self.env_info.PYTHONPATH.append(self.package_folder)
"""


test = """def foo(output):
    output.info("Hello Foo")
def bar(output):
    output.info("Hello Bar")
def baz(output):
    output.info("Hello Baz")
def boom(output):
    output.info("Hello Boom")
"""


reuse = """from conans import ConanFile, tools

class ToolsTest(ConanFile):
    name = "Consumer"
    version = "0.1"
    requires = "conantool/1.0@lasote/stable"
    generators = "virtualenv", "env"

    def source(self):
        with tools.pythonpath(self):
            import mytest
            mytest.baz(self.output)

    def build(self):
        with tools.pythonpath(self):
            import mytest
            mytest.foo(self.output)

    def package(self):
        with tools.pythonpath(self):
            import mytest
            mytest.boom(self.output)

    def package_info(self):
        with tools.pythonpath(self):
            import mytest
            mytest.bar(self.output)
"""

class PythonBuildTest(unittest.TestCase):

    def reuse_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        content = load(os.path.join(client.current_folder, "conanenv.txt"))
        self.assertIn("PYTHONPATH", content)
        self.assertIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        client.run("build")
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertIn("Hello Foo", client.user_io.out)

        client.run("export lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("remove Consumer/0.1@lasote/stable -f")
        client.run("export lasote/stable")
        client.run("source Consumer/0.1@lasote/stable")
        self.assertIn("Hello Baz", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Boom", client.user_io.out)

    def source_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("source Consumer/0.1@lasote/stable")
        self.assertIn("Hello Baz", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Boom", client.user_io.out)
