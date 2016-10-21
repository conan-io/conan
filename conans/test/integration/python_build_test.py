import unittest
from conans.test.tools import TestClient
from conans.paths import CONANFILE
from conans.util.files import load
import os
from conans.model.env_info import DepsEnvInfo


class PythonBuildTest(unittest.TestCase):

    def reuse_test(self):
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
"""
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        reuse = """from conans import ConanFile, tools

class ToolsTest(ConanFile):
    requires = "conantool/1.0@lasote/stable"
    generators = "virtualenv", "env"

    def build(self):
        with tools.pythonpath(self):
            import mytest
            mytest.foo(self.output)

    def package_info(self):
        with tools.pythonpath(self):
            import mytest
            mytest.bar(self.output)
"""
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        content = load(os.path.join(client.current_folder, "conanenv.txt"))
        self.assertIn("PYTHONPATH", content)
        self.assertIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        client.run("build")
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertIn("Hello Foo", client.user_io.out)
