import os
import unittest

from conans.model.info import ConanInfo
from conans.paths import BUILD_INFO, CONANFILE
from conans.test.utils.test_files import temp_folder
from conans.test.utils.tools import TestClient, TestServer
from conans.util.files import save

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

    def test_reuse_package_info(self):
        # https://github.com/conan-io/conan/issues/2644
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")
        reuse = """from conans import ConanFile, tools
class ToolsTest(ConanFile):
    name = "Consumer"
    version = "0.1"
    requires = "conantool/1.0@lasote/stable"

    def package_info(self):
        import mytest
        mytest.bar(self.output)
"""
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("create . conan/testing")
        self.assertIn("Consumer/0.1@conan/testing: Hello Bar", client.out)

    def test_reuse_build(self):
        # https://github.com/conan-io/conan/issues/2644
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")
        reuse = """from conans import ConanFile
class ToolsTest(ConanFile):
    name = "Consumer"
    version = "0.1"
    requires = "conantool/1.0@lasote/stable"

    def build(self):
        import mytest
        mytest.foo(self.output)
"""
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("create . conan/testing")
        self.assertIn("Consumer/0.1@conan/testing: Hello Foo", client.out)
        self.assertNotIn("WARN: Linter. Line 8: Unable to import 'mytest'", client.out)

    def test_reuse_source(self):
        # https://github.com/conan-io/conan/issues/2644
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")
        reuse = """from conans import ConanFile
class ToolsTest(ConanFile):
    name = "Consumer"
    version = "0.1"
    requires = "conantool/1.0@lasote/stable"

    def source(self):
        import mytest
        mytest.baz(self.output)
"""
        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("create . conan/testing")
        self.assertIn("Consumer/0.1@conan/testing: Hello Baz", client.out)
        self.assertNotIn("WARN: Linter. Line 8: Unable to import 'mytest'", client.out)

    def test_reuse(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        self.assertNotIn("Hello Bar", client.out)  # IMPORTANT!! WTF? Why this test was passing? Why I'm missing?
        self.assertNotIn("Hello Foo", client.out)
        client.run("build .")
        self.assertNotIn("Hello Bar", client.out)
        self.assertIn("Hello Foo", client.out)

        client.run("package . -pf=mypkg")
        self.assertNotIn("Hello Bar", client.out)
        self.assertIn("Hello Boom", client.out)

        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("export-pkg . lasote/stable -f")
        self.assertIn("Hello Boom", client.out)

    def test_upload_reuse(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("upload conantool/1.0@lasote/stable --all")
        client.run("remove * -f")
        client.run("search")
        self.assertNotIn("lasote/stable", client.out)
        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)
        # Try again, just in case
        client.run("upload conantool/1.0@lasote/stable --all")
        client.run("remove * -f -r=default")
        client.run("upload conantool/1.0@lasote/stable --all")

    def test_basic_install(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        self.assertNotIn("Unable to import 'mytest'", client.out)
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

    def test_basic_package(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

    def test_basic_source(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        client.run("source .")
        self.assertIn("Hello Baz", client.out)
        self.assertNotIn("Hello Foo", client.out)
        self.assertNotIn("Hello Bar", client.out)
        self.assertNotIn("Hello Boom", client.out)

    def test_errors(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        # BUILD_INFO is created by default, remove it to check message
        os.remove(os.path.join(client.current_folder, BUILD_INFO))
        client.run("source .", assert_error=True)
        # Output in py3 is different, uses single quote
        # Now it works automatically without the env generator file
        self.assertIn("No module named mytest", str(client.out).replace("'", ""))

    def test_pythonpath_env_injection(self):

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
        client.run("export . lasote/stable")

        # We can't build the package without our PYTHONPATH
        self.assertRaises(Exception, client.run,
                          "install conantool/1.0@lasote/stable --build missing")

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
        client.run("install . --build -e PYTHONPATH=['%s']" % external_dir)
        client.run("build .")
        info = ConanInfo.loads(client.load("conaninfo.txt"))
        pythonpath = info.env_values.env_dicts(None)[1]["PYTHONPATH"]
        self.assertEqual(os.path.normpath(pythonpath[0]), os.path.normpath(external_dir))
        self.assertTrue(len(pythonpath), 2)

    def test_external_python_with_simple_var(self):
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
        client.run("export . lasote/stable")
        # Should work even if PYTHONPATH is not declared as [], only external resource needed
        client.run('install Hello/0.1@lasote/stable --build missing -e PYTHONPATH="%s"'
                   % external_dir)
