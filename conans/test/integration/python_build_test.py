import unittest
from conans.test.utils.tools import TestClient, TestServer
from conans.paths import CONANFILE, CONANENV, BUILD_INFO
from conans.util.files import load, save
import os
from conans.test.utils.test_files import temp_folder
from conans.model.info import ConanInfo
from conans.model.env_info import EnvValues


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
        client.run("install .  -g txt -g env")
        content = load(os.path.join(client.current_folder, CONANENV))
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

    def upload_reuse_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("upload conantool/1.0@lasote/stable --all")
        client.run("remove * -f")
        client.run("search")
        self.assertNotIn("lasote/stable", client.user_io.out)
        client.run("export lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)
        # Try again, just in case
        client.run("upload conantool/1.0@lasote/stable --all")
        client.run("remove * -f -r=default")
        client.run("upload conantool/1.0@lasote/stable --all")

    def basic_install_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

    def basic_package_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build", ignore_error=True)
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("package Consumer/0.1@lasote/stable")

    def basic_source_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("install -g txt")
        client.run("source Consumer/0.1@lasote/stable")
        self.assertIn("Hello Baz", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Boom", client.user_io.out)

    def errors_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export lasote/stable")
        client.run("install")
        # BUILD_INFO is created by default, remove it to check message
        os.remove(os.path.join(client.current_folder, BUILD_INFO))
        client.run("source Consumer/0.1@lasote/stable")
        self.assertNotIn("Consumer/0.1@lasote/stable: WARN: conanbuildinfo.txt file not found",
                         client.user_io.out)
        # Output in py3 is different, uses single quote
        # Now it works automatically without the env generator file
        self.assertNotIn("No module named mytest", str(client.user_io.out).replace("'", ""))

    def pythonpath_env_injection_test(self):

        # Save some custom python code in custom dir
        external_py = '''
def external_baz():
    print("External baz")

'''
        external_dir = temp_folder()
        save(os.path.join(external_dir, "external.py"), external_py)

        conanfile = """

import os
from conans import ConanFile, tools

class ConanToolPackage(ConanFile):
    name = "conantool"
    version = "1.0"
    exports = "*"
    build_policy = "missing"

    def build(self):
        with tools.pythonpath(self):
            import external
            external.external_baz()

    def package(self):
        self.copy("*")

    def package_info(self):
        self.env_info.PYTHONPATH.append(self.package_folder)
"""
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export lasote/stable")

        # We can't build the package without our PYTHONPATH
        self.assertRaises(Exception, client.run, "install conantool/1.0@lasote/stable --build missing")

        # But we can inject the PYTHONPATH
        client.run("install conantool/1.0@lasote/stable -e PYTHONPATH=['%s']" % external_dir)

        # Now we want to reuse the package and access both external stuff and mytest.py stuff

        reuse = """from conans import ConanFile, tools

class ToolsTest(ConanFile):
    name = "Consumer"
    version = "0.1"
    requires = "conantool/1.0@lasote/stable"

    def build(self):
        with tools.pythonpath(self):
            import mytest
            mytest.foo(self.output)
            import external
            external.external_baz()
"""
        client.save({CONANFILE: reuse})
        client.run("install --build -e PYTHONPATH=['%s']" % external_dir)
        client.run("build")
        info = ConanInfo.loads(load(os.path.join(client.current_folder, "conaninfo.txt")))
        pythonpath = info.env_values.env_dicts(None)[1]["PYTHONPATH"]
        self.assertEquals(os.path.normpath(pythonpath[0]), os.path.normpath(external_dir))
        self.assertTrue(len(pythonpath), 2)

    def external_python_with_simple_var_test(self):
        client = TestClient()
        conanfile_simple = """from conans import ConanFile, tools

class ToolsTest(ConanFile):
    name = "Hello"
    version = "0.1"

    def build(self):
        with tools.pythonpath(self):
            import external
            external.external_baz()

    """
        external_py = '''
def external_baz():
    print("External baz")

            '''
        external_dir = temp_folder()
        save(os.path.join(external_dir, "external.py"), external_py)

        client.save({CONANFILE: conanfile_simple})
        client.run("export lasote/stable")
        # Should work even if PYTHONPATH is not declared as [], only external resource needed
        client.run('install Hello/0.1@lasote/stable --build missing -e PYTHONPATH="%s"' % external_dir)
