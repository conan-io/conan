import unittest
from conans.test.utils.tools import TestClient, TestServer,\
    create_local_git_repo
from conans.paths import CONANFILE, BUILD_INFO
from conans.util.files import load, save
import os
from conans.test.utils.test_files import temp_folder
from conans.model.info import ConanInfo


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


class PythonExtendTest(unittest.TestCase):
    def _define_base(self, client):
        conanfile = """from conans import ConanFile
class MyConanfileBase(ConanFile):
    def source(self):
        self.output.info("My cool source!")
    def build(self):
        self.output.info("My cool build!")
    def package(self):
        self.output.info("My cool package!")
    def package_info(self):
        self.output.info("My cool package_info!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . MyConanfileBase/1.1@lasote/testing")

    def reuse_test(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        self._define_base(client)
        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)

    def reuse_version_ranges_test(self):
        client = TestClient()
        self._define_base(client)
        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/[>1.0,<1.2]@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Python requires", str(client.out).splitlines())
        self.assertIn("    MyConanfileBase/1.1@lasote/testing", str(client.out).splitlines())
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

    def invalid_test(self):
        client = TestClient()
        reuse = """from conans import ConanFile, python_requires
class PkgTest(ConanFile):
    def source(self):
        base = python_requires("MyConanfileBase/1.0@lasote/testing")
"""

        client.save({"conanfile.py": reuse})
        error = client.run("create . Pkg/0.1@lasote/testing", ignore_error=True)
        self.assertTrue(error)
        self.assertIn("ERROR: Pkg/0.1@lasote/testing: Error in source() method, line 4", client.out)
        self.assertIn('base = python_requires("MyConanfileBase/1.0@lasote/testing', client.out)
        self.assertIn("Invalid use of python_requires(MyConanfileBase/1.0@lasote/testing)", client.out)

    def transitive_multiple_reuse_test(self):
        client = TestClient()
        conanfile = """from conans import ConanFile
class SourceBuild(ConanFile):
    def source(self):
        self.output.info("My cool source!")
    def build(self):
        self.output.info("My cool build!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . SourceBuild/1.0@user/channel")

        conanfile = """from conans import ConanFile
class PackageInfo(ConanFile):
    def package(self):
        self.output.info("My cool package!")
    def package_info(self):
        self.output.info("My cool package_info!")
"""
        client.save({"conanfile.py": conanfile})
        client.run("export . PackageInfo/1.0@user/channel")

        conanfile = """from conans import ConanFile, python_requires
source = python_requires("SourceBuild/1.0@user/channel")
package = python_requires("PackageInfo/1.0@user/channel")
class MyConanfileBase(source.SourceBuild, package.PackageInfo):
    pass
"""
        client.save({"conanfile.py": conanfile})
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

    def local_import_test(self):
        client = TestClient(servers={"default": TestServer()},
                            users={"default": [("lasote", "mypass")]})
        conanfile = """from conans import ConanFile
import mydata
class MyConanfileBase(ConanFile):
    exports = "*.py"
    def source(self):
        self.output.info(mydata.src)
    def build(self):
        self.output.info(mydata.build)
    def package(self):
        self.output.info(mydata.pkg)
    def package_info(self):
        self.output.info(mydata.info)
"""
        mydata = """src = "My cool source!"
build = "My cool build!"
pkg = "My cool package!"
info = "My cool package_info!"
"""
        client.save({"conanfile.py": conanfile,
                     "mydata.py": mydata})
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        reuse = """from conans import ConanFile, python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    pass
"""

        client.save({"conanfile.py": reuse}, clean_first=True)
        client.run("create . Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool source!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool build!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package!", client.out)
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)

        client.run("upload * --all --confirm")
        client.run("remove * -f")
        client.run("install Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: My cool package_info!", client.out)
        client.run("remove * -f")
        client.run("download Pkg/0.1@lasote/testing")
        self.assertIn("Pkg/0.1@lasote/testing: Package installed 5ab84d6acfe1f23c4fae0ab88f26e3a396351ac9",
                      client.out)

    def reuse_scm_test(self):
        client = TestClient()

        conanfile = """from conans import ConanFile
scm = {"type" : "git",
       "url" : "somerepo",
       "revision" : "auto"}

class MyConanfileBase(ConanFile):
    scm = scm
"""
        create_local_git_repo({"conanfile.py": conanfile}, branch="my_release",
                              folder=client.current_folder)
        client.run("export . MyConanfileBase/1.1@lasote/testing")
        client.run("get MyConanfileBase/1.1@lasote/testing")
        # The global scm is left as-is
        self.assertIn("""scm = {"type" : "git",
       "url" : "somerepo",
       "revision" : "auto"}""", client.out)
        # but the class one is replaced
        self.assertNotIn("scm = scm", client.out)
        self.assertIn('    scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "somerepo"', client.out)

        reuse = """from conans import python_requires
base = python_requires("MyConanfileBase/1.1@lasote/testing")
class PkgTest(base.MyConanfileBase):
    scm = base.scm
    other = 123
    def _my_method(self):
        pass
"""
        client.save({"conanfile.py": reuse})
        client.run("export . Pkg/0.1@lasote/testing")
        client.run("get Pkg/0.1@lasote/testing")
        self.assertNotIn("scm = base.scm", client.out)
        self.assertIn('scm = {"revision":', client.out)
        self.assertIn('"type": "git",', client.out)
        self.assertIn('"url": "somerepo"', client.out)


class PythonBuildTest(unittest.TestCase):

    def reuse_package_info_test(self):
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

    def reuse_build_test(self):
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

    def reuse_source_test(self):
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

    def reuse_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        self.assertNotIn("Hello Bar", client.user_io.out)  # IMPORTANT!! WTF? Why this test was passing? Why I'm missing?
        self.assertNotIn("Hello Foo", client.user_io.out)
        client.run("build .")
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertIn("Hello Foo", client.user_io.out)

        client.run("package . -pf=mypkg")
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertIn("Hello Boom", client.user_io.out)

        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("export-pkg . lasote/stable -f")
        self.assertIn("Hello Boom", client.out)

    def upload_reuse_test(self):
        server = TestServer()
        servers = {"default": server}
        client = TestClient(servers=servers, users={"default": [("lasote", "mypass")]})
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

        client.run("upload conantool/1.0@lasote/stable --all")
        client.run("remove * -f")
        client.run("search")
        self.assertNotIn("lasote/stable", client.user_io.out)
        client.run("export . lasote/stable")
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
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        self.assertNotIn("Unable to import 'mytest'", client.out)
        client.run("install Consumer/0.1@lasote/stable --build")
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

    def basic_package_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("export . lasote/stable")
        client.run("install Consumer/0.1@lasote/stable --build", ignore_error=True)
        lines = [line.split(":")[1] for line in str(client.user_io.out).splitlines()
                 if line.startswith("Consumer/0.1@lasote/stable: Hello")]
        self.assertEqual([' Hello Baz', ' Hello Foo', ' Hello Boom', ' Hello Bar'],
                         lines)

    def basic_source_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        client.run("source .")
        self.assertIn("Hello Baz", client.user_io.out)
        self.assertNotIn("Hello Foo", client.user_io.out)
        self.assertNotIn("Hello Bar", client.user_io.out)
        self.assertNotIn("Hello Boom", client.user_io.out)

    def errors_test(self):
        client = TestClient()
        client.save({CONANFILE: conanfile, "__init__.py": "", "mytest.py": test})
        client.run("export . lasote/stable")

        client.save({CONANFILE: reuse}, clean_first=True)
        client.run("install .")
        # BUILD_INFO is created by default, remove it to check message
        os.remove(os.path.join(client.current_folder, BUILD_INFO))
        client.run("source .", ignore_error=True)
        # Output in py3 is different, uses single quote
        # Now it works automatically without the env generator file
        self.assertIn("No module named mytest", str(client.user_io.out).replace("'", ""))

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
        client.run("export . lasote/stable")

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
        client.run("install . --build -e PYTHONPATH=['%s']" % external_dir)
        client.run("build .")
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
        client.run("export . lasote/stable")
        # Should work even if PYTHONPATH is not declared as [], only external resource needed
        client.run('install Hello/0.1@lasote/stable --build missing -e PYTHONPATH="%s"' % external_dir)
